import pandas as pd
import io
import json
import matplotlib.pyplot as plt
import matplotlib
import os
import base64
from flask import Flask, render_template, request, redirect, url_for, flash, session

# SỬA LỖI 1: Cần Agg backend để matplotlib hoạt động trên môi trường không giao diện
matplotlib.use('Agg') 

# SỬA LỖI 2: TRỎ template_folder về thư mục gốc để Flask tìm thấy HTML
app = Flask(__name__, template_folder='.') 
app.secret_key = 'your_secret_key_very_secure'

# --- KHỞI TẠO VÀ XỬ LÝ DATAFRAME ---

def initialize_dataframe():
    """Khởi tạo DataFrame rỗng với các cột chuẩn."""
    cols = ['Tên', 'Khối', 'Lớp', 'Môn', 'HK', 'TX1', 'TX2', 'TX3', 'TX4', 'GK', 'CK']
    df = pd.DataFrame(columns=cols)
    score_cols = ['TX1', 'TX2', 'TX3', 'TX4', 'GK', 'CK']
    for col in score_cols:
        # Sử dụng 'float' để xử lý NaN (giá trị thiếu) một cách an toàn
        df[col] = pd.to_numeric(df[col], errors='coerce').astype('float')
    return df

# SỬA LỖI 3: Dùng orient='split' để lưu JSON an toàn hơn cho Pandas
def save_df(df):
    """Lưu DataFrame vào session."""
    if df is not None and not df.empty:
        session['df_data'] = df.to_json(orient='split')
    else:
        # Xóa dữ liệu cũ nếu DataFrame rỗng
        session.pop('df_data', None)

# SỬA LỖI 4: Xử lý ngoại lệ để tránh lỗi 500 khi session hỏng hoặc không tồn tại
def load_df():
    """Tải DataFrame từ session. TRẢ VỀ DataFrame RỖNG nếu gặp lỗi."""
    if 'df_data' in session:
        df_json = session['df_data']
        try:
            # Đảm bảo dùng orient='split' khi đọc
            df = pd.read_json(df_json, orient='split')
            # Đảm bảo các cột điểm vẫn là float sau khi đọc
            score_cols = ['TX1', 'TX2', 'TX3', 'TX4', 'GK', 'CK']
            for col in score_cols:
                 df[col] = pd.to_numeric(df[col], errors='coerce').astype('float')
            return df
        except Exception as e:
            # Nếu có lỗi (dữ liệu JSON hỏng), in lỗi ra console và khởi tạo lại DF
            print(f"LỖI TẢI DATAFRAME TỪ SESSION: {e}")
            session.pop('df_data', None)
            return initialize_dataframe()
            
    return initialize_dataframe()

# Hàm tính điểm TB (Giữ nguyên)
def calculate_average_score(row):
    scores = {}
    for col, weight in [('TX1', 1), ('TX2', 1), ('TX3', 1), ('TX4', 1), ('GK', 2), ('CK', 3)]:
        # Bỏ qua NaN
        if pd.notna(row[col]):
            scores[col] = (row[col], weight)
    
    if not scores:
        return pd.NA # Không có điểm nào, trả về NA (Not Available)

    total_score = sum(score * weight for score, weight in scores.values())
    total_weight = sum(weight for score, weight in scores.values())
    
    return total_score / total_weight if total_weight > 0 else pd.NA

# --- CÁC HÀM ROUTE (ĐÃ ĐƠN GIẢN HÓA VÀ KẾT NỐI VỚI load_df) ---

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
                # Đọc file CSV
                file_content = file.read().decode('utf-8')
                df = pd.read_csv(io.StringIO(file_content))
                
                # Áp dụng logic chuẩn hóa và lưu
                df = df.rename(columns=lambda x: x.strip())
                df = df.fillna(pd.NA)
                
                # Khởi tạo lại các cột điểm để đảm bảo kiểu float
                score_cols = ['TX1', 'TX2', 'TX3', 'TX4', 'GK', 'CK']
                for col in score_cols:
                     df[col] = pd.to_numeric(df[col], errors='coerce').astype('float')
                
                # SỬA LỖI 5: Đảm bảo DF được lưu ngay sau khi tải lên thành công
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
    
    # Chuẩn bị danh sách cho form (Sử dụng .unique() để lấy các giá trị duy nhất)
    # Nếu df rỗng, list() sẽ trả về danh sách rỗng, template vẫn chạy an toàn
    student_names = df['Tên'].dropna().unique().tolist() if 'Tên' in df.columns else []
    grades = df['Khối'].dropna().unique().tolist() if 'Khối' in df.columns else []
    classes = df['Lớp'].dropna().unique().tolist() if 'Lớp' in df.columns else []
    subjects = df['Môn'].dropna().unique().tolist() if 'Môn' in df.columns else []
    semesters = df['HK'].dropna().unique().tolist() if 'HK' in df.columns else ['HK1', 'HK2'] # Default values

    # Sắp xếp DataFrame để hiển thị đẹp hơn
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
    name = request.form.get('name_new') # Lấy tên học sinh mới (nhập thủ công)
    grade = request.form.get('grade')
    class_name = request.form.get('class')
    subject = request.form.get('subject')
    semester = request.form.get('semester')
    diem_column = request.form.get('diem_column')
    diem_value = request.form.get('diem_value')

    if not all([name, grade, class_name, subject, semester, diem_column, diem_value]):
        flash('Vui lòng điền đầy đủ thông tin.', 'error')
        return redirect(url_for('manage_scores'))
    
    try:
        score = float(diem_value)
        if not (0.0 <= score <= 10.0):
            flash('Điểm phải nằm trong khoảng 0.0 đến 10.0.', 'error')
            return redirect(url_for('manage_scores'))

        # Tìm dòng cần cập nhật (hoặc tạo dòng mới)
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
                'HK': semester,
                'TX1': pd.NA, 'TX2': pd.NA, 'TX3': pd.NA, 'TX4': pd.NA, 'GK': pd.NA, 'CK': pd.NA,
                diem_column: score # Cập nhật điểm ngay lập tức
            }
            # Thêm dòng mới vào DataFrame
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            flash(f'Thêm điểm mới ({score}) cho học sinh {name} thành công!', 'success')
        else:
            # Cập nhật điểm trên dòng đã tồn tại
            df.loc[filter_mask, diem_column] = score
            flash(f'Cập nhật điểm {diem_column} ({score}) cho {name} thành công!', 'success')

        save_df(df) # Lưu DataFrame đã cập nhật vào session
        
    except ValueError:
        flash('Giá trị điểm không hợp lệ.', 'error')
    except Exception as e:
        flash(f'Lỗi không xác định khi cập nhật điểm: {e}', 'error')

    return redirect(url_for('manage_scores'))

@app.route('/report')
def report():
    df = load_df()
    report_data = {}

    if df.empty:
        return render_template('bao_cao.html', report_data=None)

    # Thêm cột điểm trung bình (TB)
    df['TB'] = df.apply(calculate_average_score, axis=1)

    # Phân tích theo Khối
    for grade in df['Khối'].dropna().unique():
        df_grade = df[df['Khối'] == grade].copy()
        subjects_data = {}
        
        # Phân tích theo Môn học
        for subject in df_grade['Môn'].dropna().unique():
            df_subject = df_grade[df_grade['Môn'] == subject].copy()
            
            # Tính toán thống kê
            total_students = len(df_subject)
            passed_students_df = df_subject[df_subject['TB'] >= 5.0].dropna(subset=['TB'])
            passed_count = len(passed_students_df)
            
            avg_score = df_subject['TB'].mean()
            pass_rate = (passed_count / total_students) * 100 if total_students > 0 else 0
            
            passed_students = passed_students_df['Tên'].tolist()
            # Học sinh chưa đạt là những người có điểm TB < 5.0
            failed_students = df_subject[(df_subject['TB'] < 5.0) & (df_subject['TB'].notna())]['Tên'].tolist()
            
            subjects_data[subject] = {
                'avg_score': avg_score,
                'pass_rate': pass_rate,
                'passed_students': passed_students,
                'failed_students': failed_students
            }

        # Tạo Biểu đồ (Plotting)
        chart_base64 = None
        if not df_grade['TB'].dropna().empty:
            plt.figure(figsize=(10, 6))
            df_grade['TB'].plot(kind='hist', bins=10, edgecolor='black', color='#6E79EC')
            plt.title(f'Phân bố Điểm TB Khối {grade}')
            plt.xlabel('Điểm Trung Bình')
            plt.ylabel('Số lượng Học sinh')
            
            # Đánh dấu ngưỡng 5.0
            plt.axvline(x=5.0, color='#FF3B30', linestyle='--', linewidth=1.5, label='Ngưỡng Đạt')
            plt.legend()
            
            # Lưu biểu đồ vào bộ nhớ đệm và chuyển thành base64
            img = io.BytesIO()
            plt.savefig(img, format='png')
            img.seek(0)
            chart_base64 = base64.b64encode(img.getvalue()).decode()
            plt.close() # Đóng figure để giải phóng bộ nhớ

        report_data[grade] = {
            'subjects': subjects_data,
            'chart_base64': chart_base64
        }

    return render_template('bao_cao.html', report_data=report_data)

if __name__ == '__main__':
    # Lưu ý: Khi deploy trên GitHub Pages, server tự chạy, không dùng if __name__ == '__main__'
    app.run(debug=True)