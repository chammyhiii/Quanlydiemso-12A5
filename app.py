# app.py
from flask import Flask, render_template, request, url_for, flash, redirect # Đã thêm flash và redirect
import pandas as pd
import matplotlib.pyplot as plt
import os
import random
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_super_secure_key_12345' # Cần có SECRET_KEY để sử dụng flash

# Tên file dữ liệu
DATA_FILE = 'du_lieu_hoc_sinh.csv'

# Kiểm tra và tạo file dữ liệu nếu không tồn tại
def initialize_data_file():
    if not os.path.exists(DATA_FILE):
        df = pd.DataFrame(columns=[
            'Tên', 'Khối', 'Lớp', 'Môn', 'HK', 'TX1', 'TX2', 'TX3', 'TX4', 'GK', 'CK'
        ])
        df.to_csv(DATA_FILE, index=False)

# Tính điểm trung bình môn
def calculate_avg(row):
    try:
        tx_scores = [
            row['TX1'], row['TX2'], row['TX3'], row['TX4']
        ]
        # Lọc bỏ các giá trị NaN/None
        valid_tx_scores = [s for s in tx_scores if pd.notna(s)]
        tx_sum = sum(valid_tx_scores)
        tx_count = len(valid_tx_scores)

        gk_score = row['GK'] if pd.notna(row['GK']) else 0
        ck_score = row['CK'] if pd.notna(row['CK']) else 0

        # Trọng số cho điểm thường xuyên, giữa kỳ, cuối kỳ
        tx_weight = 1
        gk_weight = 2
        ck_weight = 3

        if tx_count > 0:
            tx_avg = tx_sum / tx_count
        else:
            tx_avg = 0

        total_score = (tx_avg * tx_weight) + (gk_score * gk_weight) + (ck_score * ck_weight)
        total_weight = tx_weight + gk_weight + ck_weight

        # Tránh chia cho 0 nếu không có điểm nào được nhập
        return total_score / total_weight if total_weight > 0 else None
    except Exception:
        return None

# Tạo biểu đồ và lưu vào thư mục static
def generate_chart(data):
    # Lấy 10 môn học ngẫu nhiên từ dữ liệu
    subjects = list(data.keys())
    random.shuffle(subjects)
    selected_subjects = subjects[:min(10, len(subjects))]

    scores = [data[subject] for subject in selected_subjects]
    
    # Thiết lập kích thước và độ phân giải
    plt.figure(figsize=(12, 8), dpi=100)
    
    # Tạo biểu đồ cột với màu sắc đẹp mắt
    colors = ['#7B85F1', '#58E6D9', '#FFA5D3', '#5AC8FA', '#FFD166']
    # Sử dụng một màu ngẫu nhiên cho toàn bộ cột để biểu đồ đồng nhất hơn
    color_choice = random.choice(colors) 
    plt.bar(selected_subjects, scores, color=color_choice, edgecolor='none', alpha=0.8)
    
    # Tiêu đề và nhãn
    plt.title('Phân bổ điểm số môn học', fontsize=18, fontweight='bold', color='#2D3748')
    plt.xlabel('Môn học', fontsize=12, color='#4A5568')
    plt.ylabel('Điểm trung bình', fontsize=12, color='#4A5568')
    
    # Cài đặt lưới
    plt.grid(axis='y', linestyle='--', alpha=0.6)
    
    # Điều chỉnh khoảng cách nhãn trên trục x
    plt.xticks(rotation=45, ha='right')
    
    # Giới hạn trục y
    plt.ylim(0, 10)
    
    # Loại bỏ khung biểu đồ
    for spine in plt.gca().spines.values():
        spine.set_visible(False)
    
    # Lưu biểu đồ vào thư mục static
    if not os.path.exists('static'):
        os.makedirs('static')
    plt.tight_layout()
    plt.savefig('static/bieu_do.png')
    plt.close() # Đóng figure để giải phóng bộ nhớ

@app.route('/')
def index():
    initialize_data_file()
    
    try:
        df = pd.read_csv(DATA_FILE)
        # Chuyển đổi các cột điểm thành số, lỗi sẽ là NaN
        score_cols = ['TX1', 'TX2', 'TX3', 'TX4', 'GK', 'CK']
        for col in score_cols:
             # Chuyển đổi sang float, giữ lại NaN nếu không thể chuyển đổi
            df[col] = pd.to_numeric(df[col], errors='coerce') 
    except FileNotFoundError:
        df = pd.DataFrame(columns=[
            'Tên', 'Khối', 'Lớp', 'Môn', 'HK', 'TX1', 'TX2', 'TX3', 'TX4', 'GK', 'CK'
        ])
    
    # Lấy danh sách các giá trị duy nhất từ các cột
    student_names = df['Tên'].unique().tolist()
    grades = df['Khối'].unique().tolist()
    classes = df['Lớp'].unique().tolist()
    subjects = df['Môn'].unique().tolist()
    semesters = df['HK'].unique().tolist()
    
    return render_template(
        'index.html',
        student_names=student_names,
        grades=grades,
        classes=classes,
        subjects=subjects,
        semesters=semesters,
        df=df
    )

@app.route('/add_score', methods=['POST'])
def add_score():
    try:
        df = pd.read_csv(DATA_FILE)
        # Chuyển đổi các cột điểm thành số, lỗi sẽ là NaN
        score_cols = ['TX1', 'TX2', 'TX3', 'TX4', 'GK', 'CK']
        for col in score_cols:
             # Chuyển đổi sang float, giữ lại NaN nếu không thể chuyển đổi
            df[col] = pd.to_numeric(df[col], errors='coerce')
    except FileNotFoundError:
        df = pd.DataFrame(columns=[
            'Tên', 'Khối', 'Lớp', 'Môn', 'HK', 'TX1', 'TX2', 'TX3', 'TX4', 'GK', 'CK'
        ])
    
    name = request.form['name']
    grade = request.form['grade']
    class_name = request.form['class']
    subject = request.form['subject']
    semester = request.form['semester']

    scores = {}
    is_valid_input = True
    for key in ['tx1', 'tx2', 'tx3', 'tx4', 'gk', 'ck']:
        # Xử lý input rỗng và kiểm tra giá trị hợp lệ
        input_value = request.form.get(key)
        if input_value:
            try:
                score_float = float(input_value)
                if 0 <= score_float <= 10:
                    scores[key.upper()] = score_float
                else:
                    is_valid_input = False
                    break # Thoát nếu điểm không hợp lệ (ngoài 0-10)
            except ValueError:
                is_valid_input = False
                break # Thoát nếu không phải là số
        else:
            scores[key.upper()] = None
    
    if not is_valid_input:
        flash("Lỗi: Điểm phải là số từ 0 đến 10.", 'error')
        return redirect(url_for('index'))

    new_data = {
        'Tên': name,
        'Khối': grade,
        'Lớp': class_name,
        'Môn': subject,
        'HK': semester,
        **scores
    }

    # Cập nhật hoặc thêm dữ liệu
    existing_row_index = df[
        (df['Tên'] == name) &
        (df['Môn'] == subject) &
        (df['HK'] == semester)
    ].index
    
    if not existing_row_index.empty:
        # Cập nhật các cột điểm
        df.loc[existing_row_index, 'TX1':'CK'] = [
            new_data['TX1'], new_data['TX2'], new_data['TX3'], new_data['TX4'], new_data['GK'], new_data['CK']
        ]
        # Đảm bảo các cột Khối và Lớp cũng được cập nhật
        df.loc[existing_row_index, 'Khối'] = new_data['Khối']
        df.loc[existing_row_index, 'Lớp'] = new_data['Lớp']
    else:
        df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)

    df.to_csv(DATA_FILE, index=False)
    
    flash("Điểm đã được thêm/cập nhật thành công!", 'success')
    return redirect(url_for('index')) # CHUYỂN HƯỚNG VỀ TRANG CHỦ

@app.route('/edit_score', methods=['POST'])
def edit_score():
    try:
        df = pd.read_csv(DATA_FILE)
        # Đảm bảo các cột điểm là kiểu số
        score_cols = ['TX1', 'TX2', 'TX3', 'TX4', 'GK', 'CK']
        for col in score_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce') 
    except FileNotFoundError:
        flash("Lỗi: Không tìm thấy file dữ liệu.", 'error')
        return redirect(url_for('index'))
    
    name = request.form['name']
    subject = request.form['subject']
    semester = request.form['semester']
    score_type = request.form['score_type']
    new_score = request.form['new_score']

    try:
        new_score_float = float(new_score) if new_score else None
        if new_score_float is not None and (new_score_float < 0 or new_score_float > 10):
             flash("Lỗi: Điểm mới phải nằm trong khoảng từ 0 đến 10.", 'error')
             return redirect(url_for('index'))
    except ValueError:
        flash("Lỗi: Điểm mới không hợp lệ. Vui lòng nhập số.", 'error')
        return redirect(url_for('index'))

    row_index = df[
        (df['Tên'] == name) &
        (df['Môn'] == subject) &
        (df['HK'] == semester)
    ].index

    if not row_index.empty:
        # Cập nhật điểm
        df.loc[row_index, score_type] = new_score_float
        df.to_csv(DATA_FILE, index=False)
        
        flash("Cập nhật điểm thành công!", 'success')
        return redirect(url_for('index')) # CHUYỂN HƯỚNG VỀ TRANG CHỦ
    else:
        flash(f"Lỗi: Không tìm thấy dữ liệu của học sinh '{name}' môn '{subject}' HK '{semester}' để sửa.", 'error')
        return redirect(url_for('index')) # CHUYỂN HƯỚNG VỀ TRANG CHỦ

@app.route('/delete_score', methods=['POST'])
def delete_score():
    try:
        df = pd.read_csv(DATA_FILE)
    except FileNotFoundError:
        flash("Lỗi: Không tìm thấy file dữ liệu.", 'error')
        return redirect(url_for('index'))

    name = request.form['name']
    subject = request.form['subject']
    semester = request.form['semester']
    
    # Số lượng hàng trước khi xóa
    initial_count = len(df)
    
    # Lọc các hàng giữ lại (không phải hàng cần xóa)
    df = df[~((df['Tên'] == name) & (df['Môn'] == subject) & (df['HK'] == semester))]
    
    # Kiểm tra xem có hàng nào bị xóa không
    if len(df) < initial_count:
        df.to_csv(DATA_FILE, index=False)
        flash("Điểm đã được xóa thành công!", 'success')
    else:
        flash(f"Lỗi: Không tìm thấy dữ liệu của học sinh '{name}' môn '{subject}' HK '{semester}' để xóa.", 'error')

    return redirect(url_for('index')) # CHUYỂN HƯỚNG VỀ TRANG CHỦ

@app.route('/report')
def report():
    try:
        df = pd.read_csv(DATA_FILE)
        # Đảm bảo các cột điểm là kiểu số trước khi tính toán
        score_cols = ['TX1', 'TX2', 'TX3', 'TX4', 'GK', 'CK']
        for col in score_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce') 
    except FileNotFoundError:
        flash("Lỗi: Không tìm thấy file dữ liệu để tạo báo cáo.", 'error')
        return redirect(url_for('index'))
    
    # Thêm cột điểm trung bình
    df['Điểm TB Môn'] = df.apply(calculate_avg, axis=1)

    # Tính điểm trung bình chung toàn bộ các môn đã có điểm
    avg_score = df['Điểm TB Môn'].mean()
    
    # Phân loại môn học
    notes = []
    pass_count = 0
    fail_count = 0
    
    # Lọc các hàng có Điểm TB Môn hợp lệ (không phải NaN)
    report_df = df.dropna(subset=['Điểm TB Môn'])
    
    for index, row in report_df.iterrows():
        if row['Điểm TB Môn'] is not None:
            # Tiêu chí: >= 5 là Đạt
            if row['Điểm TB Môn'] >= 5:
                pass_count += 1
                notes.append({
                    'type': 'Đạt',
                    'message': f"Môn '{row['Môn']}' - HK {row['HK']}: Hoàn thành tốt ({row['Điểm TB Môn']:.2f})."
                })
            else:
                fail_count += 1
                notes.append({
                    'type': 'Chưa đạt',
                    'message': f"Môn '{row['Môn']}' - HK {row['HK']}: Cần cải thiện ({row['Điểm TB Môn']:.2f})."
                })

    # Tạo dữ liệu cho biểu đồ
    subject_avg_scores = df.groupby('Môn')['Điểm TB Môn'].mean().dropna().to_dict()
    generate_chart(subject_avg_scores)
    
    return render_template(
        'bao_cao.html',
        avg_score=f"{avg_score:.2f}" if pd.notna(avg_score) else "N/A",
        notes=notes,
        pass_count=pass_count,
        fail_count=fail_count
    )

if __name__ == '__main__':
    app.run(debug=True)