from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os
import re
from calendar import monthcalendar, monthrange

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SECRET_KEY'] = 'your_secret_key_here'
db = SQLAlchemy(app)

FIXED_USERNAME = "admin"
FIXED_PASSWORD = "password"

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    tags = db.Column(db.String(500), default="")
    memo = db.Column(db.Text, default="")
    due_date = db.Column(db.String(10), default="")
    due_time = db.Column(db.String(5), default="")
    priority = db.Column(db.String(10), default="medium")
    is_recurring = db.Column(db.Boolean, default=False)
    recurrence_type = db.Column(db.String(20), default="")
    recurrence_end_date = db.Column(db.String(10), default="")
    last_generated_date = db.Column(db.String(10), default="")
    parent_recurring_id = db.Column(db.Integer, default=None)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_done = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

def login_required(route_function):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first.')
            return redirect(url_for('login'))
        return route_function(*args, **kwargs)
    wrapper.__name__ = route_function.__name__
    return wrapper

def extract_tags(title):
    """タイトルから#タグを抽出"""
    tags = re.findall(r'#(\w+)', title)
    return ','.join(tags)

def remove_tags_from_title(title):
    """タイトルから#タグを削除"""
    return re.sub(r'#\w+', '', title).strip()

def generate_recurring_tasks():
    """繰り返しタスクを生成"""
    today = datetime.now().strftime('%Y-%m-%d')
    
    recurring_tasks = Todo.query.filter_by(is_recurring=True).all()
    
    for task in recurring_tasks:
        if task.recurrence_end_date and task.recurrence_end_date < today:
            continue
        
        if not task.last_generated_date:
            task.last_generated_date = today
        
        last_date = datetime.strptime(task.last_generated_date, '%Y-%m-%d')
        today_date = datetime.strptime(today, '%Y-%m-%d')
        
        next_date = last_date
        if task.recurrence_type == 'daily':
            while next_date < today_date:
                next_date += timedelta(days=1)
        elif task.recurrence_type == 'weekly':
            while next_date < today_date:
                next_date += timedelta(weeks=1)
        elif task.recurrence_type == 'monthly':
            try:
                next_date = next_date.replace(month=next_date.month + 1)
            except ValueError:
                next_date = next_date.replace(year=next_date.year + 1, month=1)
            if next_date < today_date:
                try:
                    next_date = next_date.replace(month=next_date.month + 1)
                except ValueError:
                    next_date = next_date.replace(year=next_date.year + 1, month=1)
        
        while next_date <= today_date:
            if task.recurrence_end_date and next_date.strftime('%Y-%m-%d') > task.recurrence_end_date:
                break
            
            existing = Todo.query.filter_by(
                parent_recurring_id=task.id,
                due_date=next_date.strftime('%Y-%m-%d')
            ).first()
            
            if not existing:
                new_task = Todo(
                    title=task.title,
                    tags=task.tags,
                    memo=task.memo,
                    due_date=next_date.strftime('%Y-%m-%d'),
                    due_time=task.due_time,
                    priority=task.priority,
                    user_id=task.user_id,
                    parent_recurring_id=task.id
                )
                db.session.add(new_task)
            
            if task.recurrence_type == 'daily':
                next_date += timedelta(days=1)
            elif task.recurrence_type == 'weekly':
                next_date += timedelta(weeks=1)
            elif task.recurrence_type == 'monthly':
                try:
                    next_date = next_date.replace(month=next_date.month + 1)
                except ValueError:
                    next_date = next_date.replace(year=next_date.year + 1, month=1)
        
        task.last_generated_date = today
        db.session.commit()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username == FIXED_USERNAME and password == FIXED_PASSWORD:
            user = User.query.filter_by(username=username).first()
            if not user:
                user = User(username=username, password=password)
                db.session.add(user)
                db.session.commit()

            session['user_id'] = user.id
            flash('Login successful!')
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out')
    return redirect(url_for('login'))

@app.route("/", methods=["GET"])
@login_required
def home():
    user_id = session.get('user_id')
    search_query = request.args.get('search', '').strip()
    
    generate_recurring_tasks()
    
    todo_list = Todo.query.filter_by(user_id=user_id).all()
    
    if search_query:
        filtered_list = []
        for todo in todo_list:
            if search_query.lower() in todo.title.lower() or search_query.lower() in todo.tags.lower():
                filtered_list.append(todo)
        todo_list = filtered_list
    
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    todo_list.sort(key=lambda x: priority_order.get(x.priority, 1))
    
    return render_template("index.html", todo_list=todo_list, search_query=search_query)

@app.route("/add", methods=["POST"])
@login_required
def add():
    title = request.form.get("title")
    memo = request.form.get("memo", "")
    due_date = request.form.get("due_date", "")
    due_time = request.form.get("due_time", "")
    priority = request.form.get("priority", "medium")
    is_recurring = request.form.get("is_recurring") == "on"
    recurrence_type = request.form.get("recurrence_type", "daily") if is_recurring else ""
    recurrence_end_date = request.form.get("recurrence_end_date", "") if is_recurring else ""
    user_id = session.get('user_id')
    
    if not title:
        flash('タスク名を入力してください')
        return redirect(url_for("home"))
    
    tags = extract_tags(title)
    clean_title = remove_tags_from_title(title)
    
    new_todo = Todo(
        title=clean_title,
        tags=tags,
        memo=memo,
        due_date=due_date,
        due_time=due_time,
        priority=priority,
        is_recurring=is_recurring,
        recurrence_type=recurrence_type,
        recurrence_end_date=recurrence_end_date,
        user_id=user_id
    )
    db.session.add(new_todo)
    db.session.commit()
    
    if is_recurring:
        flash('繰り返しタスクを追加しました')
        generate_recurring_tasks()
    else:
        flash('タスクを追加しました')
    
    return redirect(url_for("home"))

@app.route("/edit/<int:todo_id>", methods=["GET", "POST"])
@login_required
def edit(todo_id):
    todo = Todo.query.filter_by(id=todo_id, user_id=session.get('user_id')).first()

    if not todo:
        flash('Task not found or you do not have permission')
        return redirect(url_for('home'))

    if request.method == 'POST':
        title = request.form.get('title')
        memo = request.form.get('memo', '')
        due_date = request.form.get('due_date', '')
        due_time = request.form.get('due_time', '')
        priority = request.form.get('priority', 'medium')
        is_recurring = request.form.get("is_recurring") == "on"
        recurrence_type = request.form.get("recurrence_type", "daily") if is_recurring else ""
        recurrence_end_date = request.form.get("recurrence_end_date", "") if is_recurring else ""
        
        tags = extract_tags(title)
        clean_title = remove_tags_from_title(title)
        
        todo.title = clean_title
        todo.tags = tags
        todo.memo = memo
        todo.due_date = due_date
        todo.due_time = due_time
        todo.priority = priority
        todo.is_recurring = is_recurring
        todo.recurrence_type = recurrence_type
        todo.recurrence_end_date = recurrence_end_date
        db.session.commit()
        flash('タスクを更新しました')
        return redirect(url_for('home'))

    return render_template('edit.html', todo=todo)

@app.route("/delete/<int:todo_id>", methods=["POST"])
@login_required
def delete(todo_id):
    todo = Todo.query.filter_by(id=todo_id, user_id=session.get('user_id')).first()

    if not todo:
        flash('Task not found or you do not have permission')
        return redirect(url_for('home'))

    db.session.delete(todo)
    db.session.commit()
    flash('タスクを削除しました')
    return redirect(url_for("home"))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('ユーザー名とパスワードを入力してください')
            return render_template('register.html')

        user = User.query.filter_by(username=username).first()
        if user:
            flash('このユーザー名は既に使われています')
            return render_template('register.html')

        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash('登録が完了しました。ログインしてください')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route("/complete/<int:todo_id>", methods=["POST"])
@login_required
def complete(todo_id):
    todo = Todo.query.filter_by(id=todo_id, user_id=session.get('user_id')).first()
    if not todo:
        flash('タスクが見つかりません')
        return redirect(url_for('home'))
    todo.is_done = True
    db.session.commit()
    flash('タスクを完了済みに追加しました')
    return redirect(url_for("home"))

@app.route("/calendar", methods=["GET"])
@login_required
def calendar_view():
    user_id = session.get('user_id')
    action = request.args.get('action', 'today')
    
    # 現在の年月を取得（セッションから）
    if 'calendar_year' not in session:
        session['calendar_year'] = datetime.now().year
    if 'calendar_month' not in session:
        session['calendar_month'] = datetime.now().month
    
    year = session.get('calendar_year', datetime.now().year)
    month = session.get('calendar_month', datetime.now().month)
    
    # ナビゲーション処理
    if action == 'prev':
        month -= 1
        if month < 1:
            month = 12
            year -= 1
    elif action == 'next':
        month += 1
        if month > 12:
            month = 1
            year += 1
    elif action == 'today':
        year = datetime.now().year
        month = datetime.now().month
    
    session['calendar_year'] = year
    session['calendar_month'] = month
    
    # 月のカレンダーを取得
    cal = monthcalendar(year, month)
    
    # タスクを取得
    all_todos = Todo.query.filter_by(user_id=user_id).all()
    
    # カレンダーデータを構築
    calendar_data = []
    today = datetime.now().date()
    
    for week in cal:
        week_data = []
        for day in week:
            if day == 0:
                # 他の月の日付
                week_data.append({
                    'day': '',
                    'other_month': True,
                    'is_today': False,
                    'tasks': []
                })
            else:
                # 当月の日付
                date_str = f"{year:04d}-{month:02d}-{day:02d}"
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                
                # その日のタスクを取得
                day_tasks = []
                for todo in all_todos:
                    if todo.due_date == date_str:
                        day_tasks.append({
                            'title': todo.title,
                            'priority': todo.priority,
                            'is_done': todo.is_done
                        })
                
                week_data.append({
                    'day': day,
                    'other_month': False,
                    'is_today': date_obj == today,
                    'tasks': day_tasks
                })
        
        calendar_data.append(week_data)
    
    # 統計情報を計算
    month_start = f"{year:04d}-{month:02d}-01"
    month_end = f"{year:04d}-{month:02d}-{monthrange(year, month)[1]:02d}"
    
    month_tasks = [t for t in all_todos if month_start <= t.due_date <= month_end]
    completed = sum(1 for t in month_tasks if t.is_done)
    incomplete = len(month_tasks) - completed
    completion_rate = int((completed / len(month_tasks) * 100)) if month_tasks else 0
    
    return render_template(
        'calendar.html',
        calendar=calendar_data,
        year=year,
        month=month,
        total_tasks=len(month_tasks),
        completed_tasks=completed,
        incomplete_tasks=incomplete,
        completion_rate=completion_rate
    )


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        user = User.query.filter_by(username=FIXED_USERNAME).first()
        if not user:
            default_user = User(username=FIXED_USERNAME, password=FIXED_PASSWORD)
            db.session.add(default_user)
            db.session.commit()
            print(f"Default user created: {FIXED_USERNAME}")

    app.run(debug=True, port=5001)