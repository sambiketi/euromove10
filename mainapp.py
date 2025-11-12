from dotenv import load_dotenv
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = "supersecretkey"

# DATABASE CONFIG
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    "DATABASE_URL", 
    "postgresql://postgres:password@localhost/euromove"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# MODELS
class Workshop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150))
    description = db.Column(db.Text)
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150))
    content = db.Column(db.Text)
    image_url = db.Column(db.String(300))
    date_posted = db.Column(db.DateTime, default=datetime.utcnow)

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(50))

# INITIALIZE DB AND CREATE DEFAULT ADMIN
with app.app_context():
    db.create_all()
    if not Admin.query.filter_by(username="admin").first():
        admin = Admin(username="admin", password="password")
        db.session.add(admin)
        db.session.commit()

# ROUTES (unchanged)
@app.route('/')
def index():
    workshops = Workshop.query.order_by(Workshop.date_posted.desc()).all()
    posts = Post.query.order_by(Post.date_posted.desc()).all()
    return render_template('frontend.html', workshops=workshops, posts=posts)

@app.route('/book', methods=['POST'])
def book():
    name = request.form.get('name')
    email = request.form.get('email')
    number = request.form.get('number')
    flash(f'Thank you {name}, your slot has been booked!', 'success')
    return redirect(url_for('index'))

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        admin = Admin.query.filter_by(username=username, password=password).first()
        if admin:
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid credentials", "danger")
    return render_template('admin_dashboard.html', login=True)

@app.route('/admin/dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        # Handle new post
        if 'post_title' in request.form:
            title = request.form.get('post_title')
            content = request.form.get('post_content')
            image_url = request.form.get('post_image')
            post = Post(title=title, content=content, image_url=image_url)
            db.session.add(post)
            db.session.commit()
            flash("Post added successfully", "success")
        # Handle new workshop
        if 'workshop_title' in request.form:
            title = request.form.get('workshop_title')
            description = request.form.get('workshop_content')
            ws = Workshop(title=title, description=description)
            db.session.add(ws)
            db.session.commit()
            flash("Workshop added successfully", "success")
    posts = Post.query.order_by(Post.date_posted.desc()).all()
    workshops = Workshop.query.order_by(Workshop.date_posted.desc()).all()
    return render_template('admin_dashboard.html', login=False, posts=posts, workshops=workshops)

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('admin_login'))
# TEST DATABASE CONNECTION
with app.app_context():
    try:
        db.session.execute(db.text("SELECT 1"))
        print("✅ Database connection successful.")
    except Exception as e:
        print("❌ Database connection failed:", e)

if __name__ == '__main__':
    app.run(debug=True)
