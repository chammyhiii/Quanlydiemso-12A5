import pandas as pd
import io
import json
import matplotlib.pyplot as plt
import matplotlib
import os
import base64
from flask import Flask, render_template, request, redirect, url_for, flash, session

# Cần Agg backend để matplotlib hoạt động trên môi trường không giao diện
matplotlib.use('Agg') 

# TRỎ template_folder về thư mục gốc để Flask tìm thấy HTML
app = Flask(__name__, template_folder='.') 
app.secret_key = 'your_secret_key_very_secure'

# Các cột điểm
SCORE_COLS = ['TX1', 'TX2', 'TX3', 'TX4', 'GK', 'CK']
# Các cột chính không phải điểm
META_COLS = ['Tên', 'Khối', 'Lớp', 'Môn', 'HK']

# --- KHỞI TẠO VÀ XỬ LÝ DATAFRAME ---

def initialize_dataframe():
    """Khởi tạo DataFrame rỗng với các cột chuẩn."""
    cols = META_COLS + SCORE_COLS
    df = pd.DataFrame(columns=cols)
    # Khởi tạo các cột điểm dưới dạng float để xử lý NaN/NA an toàn
    for col in SCORE_COLS:
        df[col] = df[col].astype('float')
    return df

def save_df(df):
    """Lưu DataFrame vào session bằng orient='split'."""
    if df is not None and not df.empty:
        # Chuyển đổi về list để đảm bảo kiểu dữ liệu chuẩn khi lưu vào session
        session['df_data'] = df.to_json(orient='split')
    else:
        session.pop('df_data', None)

def load_df():
    """Tải DataFrame từ session. TRẢ VỀ DataFrame RỖNG nếu gặp lỗi hoặc không tồn tại."""
    if 'df_data' in session:
        df_json = session['df_data']
        try:
            df = pd.read_json(df_json, orient='split')
            
            # Sửa lỗi nhập điểm (CRITICAL FIX): Đảm bảo các cột điểm luôn là float
            for col in SCORE_COLS:
                # Ép kiểu an toàn, NaN sẽ được giữ lại
                df[col] = pd.to_numeric(df[col], errors='coerce').astype('float')
                
            return df
        except Exception as e:
            # Xử lý trường hợp session hỏng
            print(f"LỖI TẢI DATAFRAME TỪ SESSION (Load/Add Score Fix): {e}")
            session.pop('df_data', None)
            return initialize_dataframe()
            
    return initialize_dataframe()

def calculate_average_score(row):
    scores = {}
    for col, weight in [('TX1', 1), ('TX2', 1), ('TX3', 1), ('TX4', 1), ('GK', 2), ('CK', 3)]:
        if pd.notna(row[col]):
            scores[col] = (row[col], weight)
    
    if not scores:
        return pd.NA 

    total_score = sum(score * weight for score, weight in scores.values())
    total_weight = sum(weight for score, weight in scores.values())
    
    return total_score / total_weight if total_weight > 0 else pd.NA

# --- CÁC HÀM ROUTE ---

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash('Không tìm thấy file tải lên.', 'error')
            return redirect(request.url)
        
        file = request.files['csv_file']
        if file.filename == '':
            flash('Vui lòng chọn file.', 'error')
            return redirect(request.url)
        
        if file and file.filename.endswith('.csv'):
            try:
                file_content = file.read().decode('utf-8')
                df = pd.read_csv(io.StringIO(file_content))
                
                df = df.rename(columns=lambda x: x.strip())
                
                # Áp dụng logic chuẩn hóa và ép kiểu ngay lập tức
                for col in META_COLS:
                    if col not in df.columns:
                        df[col] = pd.NA
                for col in SCORE_COLS:
                    df[col] = pd.to_numeric(df.get(col, pd.NA), errors='coerce').astype('float')
                
                save_df(df) 
                flash('Tải lên thành công! Dữ liệu đã sẵn sàng để phân tích.', 'success')
                return redirect(url_for('manage_scores'))

            except Exception as e:
                flash(f'Lỗi xử lý file CSV: {e}. Vui lòng kiểm tra định dạng.', 'error')
                return redirect(request.url)

    return render_template('index.html')

@app.route('/manage_scores', methods=['GET', 'POST'])
def manage_scores():
    df = load_df()
    
    student_names = df['Tên'].dropna().unique().tolist() if 'Tên' in df.columns else []
    grades = df['Khối'].dropna().unique().tolist() if 'Khối' in df.columns else []
    classes = df['Lớp'].dropna().unique().tolist() if 'Lớp' in df.columns else []
    subjects = df['Môn'].dropna().unique().tolist() if 'Môn' in df.columns else []
    semesters = df['HK'].dropna().unique().tolist() if 'HK' in df.columns else ['HK1', 'HK2'] 

    if not df.empty:
        df = df.sort_values(by=['Khối', 'Lớp', 'Môn'], na_position='first')
    
    return render_template('quan_ly_diem.html', 
                           df=df, 
                           student_names=student_names, 
                           grades=grades, 
                           classes=classes, 
                           subjects=subjects, 
                           semesters=semesters)

@app.route('/add_score', methods=['POST'])
def add_score():
    df = load_df()
    
    # Lấy dữ liệu từ form
    name = request.form.get('name_new')
    grade = request.form.get('grade')
    class_name = request.form.get('class')
    subject = request.form.get('subject')
    semester = request.form.get('semester')
    diem_column = request.form.get('diem_column')
    diem_value = request.form.get('diem_value')

    if not all([name, grade, class_name, subject, semester, diem_column, diem_value]):
        flash('Vui lòng điền đầy đủ thông tin.', 'error')
        return redirect(url_for('manage_scores'))
    
    if diem_column not in SCORE_COLS:
        flash('Cột điểm không hợp lệ.', 'error')
        return redirect(url_for('manage_scores'))

    try:
        score = float(diem_value)
        if not (0.0 <= score <= 10.0):
            flash('Điểm phải nằm trong khoảng 0.0 đến 10.0.', 'error')
            return redirect(url_for('manage_scores'))

        # Tìm dòng cần cập nhật
        filter_mask = (df['Tên'] == name) & \
                      (df['Khối'] == grade) & \
                      (df['Lớp'] == class_name) & \
                      (df['Môn'] == subject) & \
                      (df['HK'] == semester)
        
        if df[filter_mask].empty:
            # Tạo dòng mới nếu không tìm thấy
            new_row = {
                'Tên': name,
                'Khối': grade,
                'Lớp': class_name,
                'Môn': subject,
                'HK': semester
            }
            # Khởi tạo điểm mới (float)
            for col in SCORE_COLS:
                new_row[col] = pd.NA
            new_row[diem_column] = score
            
            # Sửa lỗi: Thêm dòng mới bằng pd.concat
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            flash(f'Thêm điểm mới ({score}) cho học sinh {name} thành công!', 'success')
        else:
            # Cập nhật điểm trên dòng đã tồn tại
            # Sửa lỗi: Sử dụng .loc để đảm bảo cập nhật đúng kiểu dữ liệu
            df.loc[filter_mask, diem_column] = score
            flash(f'Cập nhật điểm {diem_column} ({score}) cho {name} thành công!', 'success')

        save_df(df) # Lưu DataFrame đã cập nhật vào session
        
    except ValueError:
        flash('Giá trị điểm không hợp lệ.', 'error')
    except Exception as e:
        flash(f'Lỗi không xác định khi cập nhật điểm: {e}', 'error')
        print(f"LỖI CHI TIẾT KHI ADD SCORE: {e}")

    return redirect(url_for('manage_scores'))

@app.route('/report')
def report():
    df = load_df()
    report_data = {}

    if df.empty:
        return render_template('bao_cao.html', report_data=None)

    df['TB'] = df.apply(calculate_average_score, axis=1)

    for grade in df['Khối'].dropna().unique():
        df_grade = df[df['Khối'] == grade].copy()
        subjects_data = {}
        
        for subject in df_grade['Môn'].dropna().unique():
            df_subject = df_grade[df_grade['Môn'] == subject].copy()
            
            total_students = len(df_subject)
            passed_students_df = df_subject[df_subject['TB'] >= 5.0].dropna(subset=['TB'])
            passed_count = len(passed_students_df)
            
            avg_score = df_subject['TB'].mean()
            pass_rate = (passed_count / total_students) * 100 if total_students > 0 else 0
            
            passed_students = passed_students_df['Tên'].tolist()
            failed_students = df_subject[(df_subject['TB'] < 5.0) & (df_subject['TB'].notna())]['Tên'].tolist()
            
            subjects_data[subject] = {
                'avg_score': avg_score,
                'pass_rate': pass_rate,
                'passed_students': passed_students,
                'failed_students': failed_students
            }

        chart_base64 = None
        if not df_grade['TB'].dropna().empty:
            plt.figure(figsize=(10, 6))
            df_grade['TB'].plot(kind='hist', bins=10, edgecolor='black', color='#6E79EC')
            plt.title(f'Phân bố Điểm TB Khối {grade}')
            plt.xlabel('Điểm Trung Bình')
            plt.ylabel('Số lượng Học sinh')
            plt.axvline(x=5.0, color='#FF3B30', linestyle='--', linewidth=1.5, label='Ngưỡng Đạt')
            plt.legend()
            
            img = io.BytesIO()
            plt.savefig(img, format='png')
            img.seek(0)
            chart_base64 = base64.b64encode(img.getvalue()).decode()
            plt.close() 

        report_data[grade] = {
            'subjects': subjects_data,
            'chart_base64': chart_base64
        }

    return render_template('bao_cao.html', report_data=report_data)

# if __name__ == '__main__':
#     app.run(debug=True)