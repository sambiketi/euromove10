from dotenv import load_dotenv
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# --- Load environment variables ---
load_dotenv()

# --- Initialize Flask app ---
app = Flask(__name__)
app.secret_key = "supersecretkey"

# --- DATABASE CONFIG ---
raw_db_url = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:password@localhost/euromove"
)

# Fix Supabase URLs for SQLAlchemy + psycopg
if raw_db_url.startswith("postgres://"):
    raw_db_url = "postgresql+psycopg://" + raw_db_url[len("postgres://"):]
elif raw_db_url.startswith("postgresql://") and "+psycopg" not in raw_db_url:
    raw_db_url = "postgresql+psycopg://" + raw_db_url[len("postgresql://"):]

# Apply to Flask app
app.config['SQLALCHEMY_DATABASE_URI'] = raw_db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODELS ---
class Workshop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150))
    description = db.Column(db.Text)
    date_posted = db.Column(db.DateTime, default=datetime.now)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150))
    content = db.Column(db.Text)
    image_url = db.Column(db.String(300))
    date_posted = db.Column(db.DateTime, default=datetime.now)

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(50))

# --- INITIALIZE DATABASE AND DEFAULT ADMIN ---
with app.app_context():
    db.create_all()
    if not Admin.query.filter_by(username="admin").first():
        admin = Admin(username="admin", password="password")
        db.session.add(admin)
        db.session.commit()

# --- ROUTES ---

# Public home page
@app.route('/')
def index():
    workshops = Workshop.query.order_by(Workshop.date_posted.desc()).all()
    posts = Post.query.order_by(Post.date_posted.desc()).all()
    return render_template('frontend.html', workshops=workshops, posts=posts, datetime=datetime)

# Booking route (simple flash)
@app.route('/book', methods=['POST'])
def book():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    number = request.form.get('number', '').strip()
    flash(f'Thank you {name}, your slot has been booked!', 'success')
    return redirect(url_for('index'))

# --- ADMIN LOGIN ---
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        admin = Admin.query.filter_by(username=username, password=password).first()
        if admin:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid username or password", "danger")
    return render_template('admin_login.html')

# --- ADMIN DASHBOARD ---
@app.route('/admin/dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        # Add Post
        if 'post_title' in request.form:
            title = request.form.get('post_title', '').strip()
            content = request.form.get('post_content', '').strip()
            image_url = request.form.get('post_image', '').strip() or None

            if not title or not content:
                flash("Post title and content are required", "danger")
            else:
                try:
                    post = Post(title=title, content=content, image_url=image_url)
                    db.session.add(post)
                    db.session.commit()
                    flash("Post added successfully", "success")
                except Exception as e:
                    db.session.rollback()
                    flash(f"Error adding post: {e}", "danger")

        # Add Workshop
        if 'workshop_title' in request.form:
            title = request.form.get('workshop_title', '').strip()
            description = request.form.get('workshop_content', '').strip()

            if not title or not description:
                flash("Workshop title and description are required", "danger")
            else:
                try:
                    ws = Workshop(title=title, description=description)
                    db.session.add(ws)
                    db.session.commit()
                    flash("Workshop added successfully", "success")
                except Exception as e:
                    db.session.rollback()
                    flash(f"Error adding workshop: {e}", "danger")

    # Fetch all posts and workshops
    posts = Post.query.order_by(Post.date_posted.desc()).all()
    workshops = Workshop.query.order_by(Workshop.date_posted.desc()).all()

    return render_template('admin_dashboard.html', posts=posts, workshops=workshops, datetime=datetime)

# --- LOGOUT ---
@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

# --- TEST DB CONNECTION ---
with app.app_context():
    try:
        db.session.execute(db.text("SELECT 1"))
        print("✅ Database connection successful.")
    except Exception as e:
        print("❌ Database connection failed:", e)

# --- RUN APP ---
if __name__ == '__main__':
    app.run(debug=True)
