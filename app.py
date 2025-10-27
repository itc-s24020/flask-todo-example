from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'
app.config['SECRET_KEY'] = 'your_secret_key_here'  # Set a secret key for session management
db = SQLAlchemy(app)

# Fixed credentials for login
FIXED_USERNAME = "admin"
FIXED_PASSWORD = "password"

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_done = db.Column(db.Boolean, default=False)

# Function to check if user is logged in
def login_required(route_function):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first.')
            return redirect(url_for('login'))
        return route_function(*args, **kwargs)
    wrapper.__name__ = route_function.__name__
    return wrapper


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Check fixed credentials
        if username == FIXED_USERNAME and password == FIXED_PASSWORD:
            # Check if user exists, if not, create it
            user = User.query.filter_by(username=username).first()
            if not user:
                user = User(username=username, password=password)
                db.session.add(user)
                db.session.commit()

            # Set session
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
    todo_list = Todo.query.filter_by(user_id=user_id).all()
    return render_template("index.html", todo_list=todo_list)

@app.route("/add", methods=["POST"])
@login_required
def add():
    title = request.form.get("title")
    user_id = session.get('user_id')
    if not title:
        flash('タスク名を入力してください')
        return redirect(url_for("home"))
    new_todo = Todo(title=title, user_id=user_id)
    db.session.add(new_todo)
    db.session.commit()
    return redirect(url_for("home"))

@app.route("/edit/<int:todo_id>", methods=["GET", "POST"])
@login_required
def edit(todo_id):
    todo = Todo.query.filter_by(id=todo_id, user_id=session.get('user_id')).first()

    if not todo:
        flash('Task not found or you do not have permission')
        return redirect(url_for('home'))

    if request.method == 'POST':
        todo.title = request.form.get('title')
        db.session.commit()
        flash('Task updated successfully')
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
    flash('Task deleted successfully')
    return redirect(url_for("home"))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('ユーザー名とパスワードを入力してください')
            return render_template('register.html')

        # 既存ユーザー確認
        user = User.query.filter_by(username=username).first()
        if user:
            flash('このユーザー名は既に使われています')
            return render_template('register.html')

        # 新規ユーザー作成
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

        # Create default user if not exists
        user = User.query.filter_by(username=FIXED_USERNAME).first()
        if not user:
            default_user = User(username=FIXED_USERNAME, password=FIXED_PASSWORD)
            db.session.add(default_user)
            db.session.commit()
            print(f"Default user created: {FIXED_USERNAME}")

    app.run(debug=True, port=5001)
