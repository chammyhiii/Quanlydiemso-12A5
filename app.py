import pandas as pd
import io
import matplotlib
# Sử dụng backend không cần giao diện đồ họa
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import os
import base64 
from flask import Flask, render_template, request, redirect, url_for, flash, session

app = Flask(__name__)
app.secret_key = 'your_secret_key_very_secure'

# --- KHỞI TẠO VÀ XỬ LÝ DATAFRAME ---

def initialize_dataframe():
    """Khởi tạo DataFrame rỗng với các cột chuẩn."""
    cols = ['Tên', 'Khối', 'Lớp', 'Môn', 'HK', 'TX1', 'TX2', 'TX3', 'TX4', 'GK', 'CK']
    df = pd.DataFrame(columns=cols)
    score_cols = ['TX1', 'TX2', 'TX3', 'TX4', 'GK', 'CK']
    for col in score_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce') 
    session['df_data'] = df.to_json()

def load_df():
    """Tải DataFrame từ session."""
    if 'df_data' in session:
        try:
            df = pd.read_json(session['df_data'])
        except ValueError:
            initialize_dataframe()
            df = pd.read_json(session['df_data'])
            
        score_cols = ['TX1', 'TX2', 'TX3', 'TX4', 'GK', 'CK']
        for col in score_cols:
             df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Sửa lỗi: Loại bỏ các dòng thiếu thông tin định danh quan trọng
        df.dropna(subset=['Tên', 'Khối', 'Lớp', 'Môn', 'HK'], inplace=True)
        df.drop_duplicates(inplace=True) 
        return df
    
    initialize_dataframe() 
    return pd.read_json(session['df_data'])

def save_df(df):
    """Lưu DataFrame vào session."""
    session['df_data'] = df.to_json()

@app.before_request
def before_request():
    """Khởi tạo DataFrame nếu chưa có trong session."""
    if 'df_data' not in session:
        initialize_dataframe()

# --- HÀM TÍNH TOÁN & BIỂU ĐỒ ---

def calculate_avg_score(row):
    """Tính điểm trung bình môn theo công thức (TX1+..+TX4 + GK*2 + CK*3) / (Hệ số tổng)"""
    score_cols = ['TX1', 'TX2', 'TX3', 'TX4', 'GK', 'CK']
    scores = []
    weights = []
    weight_map = {'TX1': 1, 'TX2': 1, 'TX3': 1, 'TX4': 1, 'GK': 2, 'CK': 3}

    for col in score_cols:
        score = pd.to_numeric(row[col], errors='coerce')
        if pd.notna(score) and score >= 0:
            scores.append(score)
            weights.append(weight_map.get(col, 0))
    
    if not weights or sum(weights) == 0:
        return 0.0

    weighted_sum = sum(s * w for s, w in zip(scores, weights))
    total_weight = sum(weights)
    
    return weighted_sum / total_weight

def create_subject_avg_chart(df_grade, grade_name):
    """Vẽ biểu đồ cột Điểm TB môn theo từng môn trong Khối, trả về ảnh base64."""
    # Sửa lỗi Font cho Matplotlib (Quan trọng để hiển thị tiếng Việt)
    plt.rcParams['font.family'] = 'DejaVu Sans' 
    plt.style.use('seaborn-v0_8-whitegrid')
    
    df_grade['TB'] = df_grade.apply(calculate_avg_score, axis=1)
    df_chart = df_grade[df_grade['TB'] > 0] 
        
    if df_chart.empty:
        return None
        
    subject_avg = df_chart.groupby('Môn')['TB'].mean().sort_values(ascending=False)

    if subject_avg.empty:
        return None
        
    fig, ax = plt.subplots(figsize=(10, 5))
    primary_color = '#6E79EC'
    
    bars = ax.bar(subject_avg.index, subject_avg.values, color=primary_color, alpha=0.8)
    
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval + 0.1, round(yval, 2), ha='center', va='bottom', fontsize=10)

    ax.set_ylim(0, 10.5) 

    ax.set_title(f'Phân Bố Điểm Trung Bình Môn Học - Khối {grade_name}', fontsize=14, pad=15)
    ax.set_ylabel('Điểm Trung bình (TB)', fontsize=12)
    ax.set_xlabel('Môn Học', fontsize=12)
    plt.xticks(rotation=45, ha='right')
    plt.grid(axis='y', linestyle='--', alpha=0.6)
    plt.tight_layout()

    # Chuyển biểu đồ sang base64
    img = io.BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight')
    plt.close(fig) 
    img.seek(0)
    
    return base64.b64encode(img.getvalue()).decode('utf8')

# --- ROUTES (Không thay đổi) ---

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'csv_file' not in request.files:
            flash('Không tìm thấy file được tải lên.', 'error')
            return redirect(request.url)
        
        file = request.files['csv_file']
        
        if file.filename == '':
            flash('Chưa chọn file nào.', 'error')
            return redirect(request.url)
            
        if file and file.filename.endswith('.csv'):
            try:
                stream = io.StringIO(file.stream.read().decode("utf-8"))
                new_df = pd.read_csv(stream, delimiter=',', decimal='.', keep_default_na=True, na_values=[''])
                
                for col in ['Tên', 'Khối', 'Lớp', 'Môn', 'HK']:
                     if col in new_df.columns:
                        new_df[col] = new_df[col].astype(str).str.strip() 
                
                score_cols = ['TX1', 'TX2', 'TX3', 'TX4', 'GK', 'CK']
                for col in score_cols:
                    if col in new_df.columns:
                        new_df[col] = pd.to_numeric(new_df[col], errors='coerce')
                    else:
                        new_df[col] = pd.NA

                cols_to_keep = ['Tên', 'Khối', 'Lớp', 'Môn', 'HK'] + score_cols
                new_df = new_df[[col for col in cols_to_keep if col in new_df.columns]]
                
                new_df.dropna(subset=['Tên', 'Khối', 'Lớp', 'Môn', 'HK'], inplace=True)
                
                save_df(new_df)
                flash('Tải lên thành công! Dữ liệu đã được cập nhật.', 'success')
                return redirect(url_for('manage_scores'))
                
            except Exception as e:
                flash(f'Lỗi xử lý file CSV. Vui lòng kiểm tra định dạng cột: {e}', 'error')
                initialize_dataframe()
                return redirect(request.url)
    
    return render_template('index.html', error=request.args.get('error'))


@app.route('/manage', methods=['GET'])
def manage_scores():
    df = load_df()
    
    sort_cols = [col for col in ['Khối', 'Lớp', 'Môn', 'Tên'] if col in df.columns]
    if sort_cols:
        df_sorted = df.sort_values(by=sort_cols, ascending=True)
    else:
        df_sorted = df
        
    grades = df['Khối'].dropna().unique().tolist() if 'Khối' in df.columns else []
    classes = df['Lớp'].dropna().unique().tolist() if 'Lớp' in df.columns else []
    subjects = df['Môn'].dropna().unique().tolist() if 'Môn' in df.columns else []
    semesters = df['HK'].dropna().unique().tolist() if 'HK' in df.columns else []

    return render_template('quan_ly_diem.html', 
                           df=df_sorted, 
                           grades=grades,
                           classes=classes,
                           subjects=subjects,
                           semesters=semesters)


@app.route('/add_score', methods=['POST'])
def add_score():
    df = load_df()
    
    name = request.form.get('name_new', '').strip()
    grade = request.form.get('grade', '').strip()
    class_name = request.form.get('class', '').strip()
    subject = request.form.get('subject', '').strip()
    semester = request.form.get('semester', '').strip()
    diem_column = request.form.get('diem_column')
    diem_value_str = request.form.get('diem_value')

    if not name or not grade or not class_name or not subject or not semester or not diem_column:
        flash('Vui lòng điền đầy đủ thông tin Tên, Khối, Lớp, Môn, Học kỳ và Cột điểm.', 'error')
        return redirect(url_for('manage_scores'))
        
    try:
        diem_value = float(diem_value_str)
        if not (0.0 <= diem_value <= 10.0):
            flash('Điểm nhập vào phải từ 0.0 đến 10.0.', 'error')
            return redirect(url_for('manage_scores'))
    except ValueError:
        flash('Giá trị điểm không hợp lệ.', 'error')
        return redirect(url_for('manage_scores'))
        
    condition = (df['Tên'].str.strip() == name) & \
                (df['Khối'].str.strip() == grade) & \
                (df['Lớp'].str.strip() == class_name) & \
                (df['Môn'].str.strip() == subject) & \
                (df['HK'].str.strip() == semester)

    if condition.any():
        df.loc[condition, diem_column] = diem_value
        flash(f'Cập nhật điểm {diem_column} môn {subject} cho {name} thành công!', 'success')
    else:
        new_row = {
            'Tên': name, 
            'Khối': grade, 
            'Lớp': class_name, 
            'Môn': subject, 
            'HK': semester,
            diem_column: diem_value
        }
        score_cols = ['TX1', 'TX2', 'TX3', 'TX4', 'GK', 'CK']
        for col in score_cols:
            if col not in new_row:
                new_row[col] = pd.NA
                
        cols = ['Tên', 'Khối', 'Lớp', 'Môn', 'HK'] + score_cols
        new_df_row = pd.DataFrame([new_row], columns=cols)
        
        df = pd.concat([df, new_df_row], ignore_index=True)
        flash(f'Thêm mới điểm {diem_column} môn {subject} cho {name} thành công!', 'success')

    save_df(df)
    return redirect(url_for('manage_scores'))


@app.route('/report', methods=['GET'])
def report():
    df = load_df()
    
    if df.empty or 'Tên' not in df.columns:
        flash('Chưa có dữ liệu hoặc dữ liệu không hợp lệ để tạo báo cáo.', 'warning')
        return render_template('bao_cao.html', report_data={})

    df['TB'] = df.apply(calculate_avg_score, axis=1)
    
    report_data = {}
    grades = df['Khối'].unique().tolist()
    
    for grade in grades:
        df_grade = df[df['Khối'] == grade].copy()
        subjects_data = {}
        
        chart_base64 = create_subject_avg_chart(df_grade, grade)

        subjects = df_grade['Môn'].unique().tolist()
        
        for subject in subjects:
            df_subject = df_grade[df_grade['Môn'] == subject].copy()
            df_subject_valid = df_subject[df_subject['TB'] > 0]
            
            if df_subject_valid.empty:
                 subjects_data[subject] = {
                    'avg_score': 0.0,
                    'pass_rate': 0.0,
                    'passed_students': [],
                    'failed_students': []
                }
                 continue

            avg_score = df_subject_valid['TB'].mean()
            passed_students = df_subject_valid[df_subject_valid['TB'] >= 5.0]['Tên'].tolist()
            failed_students = df_subject_valid[df_subject_valid['TB'] < 5.0]['Tên'].tolist()
            
            total_students = len(df_subject_valid)
            pass_rate = (len(passed_students) / total_students * 100) if total_students > 0 else 0.0

            subjects_data[subject] = {
                'avg_score': avg_score,
                'pass_rate': pass_rate,
                'passed_students': passed_students,
                'failed_students': failed_students
            }
            
        report_data[grade] = {
            'chart_base64': chart_base64,
            'subjects': subjects_data
        }

    return render_template('bao_cao.html', report_data=report_data)


if __name__ == '__main__':
    import warnings
    warnings.filterwarnings("ignore", "is_categorical_dtype", module="matplotlib")
    warnings.filterwarnings("ignore", "using an implicitly registered", module="matplotlib")
    
    app.template_folder = 'templates'
    app.run(debug=True)