from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import re

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
    memo = db.Column(db.Text, default="")  # メモ欄
    due_date = db.Column(db.String(10), default="")  # 期限日（YYYY-MM-DD形式）
    priority = db.Column(db.String(10), default="medium")  # 優先度: high, medium, low
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
    
    todo_list = Todo.query.filter_by(user_id=user_id).all()
    
    if search_query:
        filtered_list = []
        for todo in todo_list:
            if search_query.lower() in todo.title.lower() or search_query.lower() in todo.tags.lower():
                filtered_list.append(todo)
        todo_list = filtered_list
    
    # 優先度順でソート（高 > 中 > 低）
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    todo_list.sort(key=lambda x: priority_order.get(x.priority, 1))
    
    return render_template("index.html", todo_list=todo_list, search_query=search_query)

@app.route("/add", methods=["POST"])
@login_required
def add():
    title = request.form.get("title")
    memo = request.form.get("memo", "")
    due_date = request.form.get("due_date", "")
    priority = request.form.get("priority", "medium")
    user_id = session.get('user_id')
    
    if not title:
        flash('タスク名を入力してください')
        return redirect(url_for("home"))
    
    tags = extract_tags(title)
    clean_title = remove_tags_from_title(title)
    
    new_todo = Todo(title=clean_title, tags=tags, memo=memo, due_date=due_date, priority=priority, user_id=user_id)
    db.session.add(new_todo)
    db.session.commit()
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
        priority = request.form.get('priority', 'medium')
        tags = extract_tags(title)
        clean_title = remove_tags_from_title(title)
        
        todo.title = clean_title
        todo.tags = tags
        todo.memo = memo
        todo.due_date = due_date
        todo.priority = priority
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