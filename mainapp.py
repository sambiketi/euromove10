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

# --- DATABASE CONFIG ---
raw_db_url = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:password@localhost/euromove"
)

# Fix Supabase URLs
if raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql+psycopg://", 1)
elif raw_db_url.startswith("postgresql://") and "+psycopg" not in raw_db_url:
    raw_db_url = raw_db_url.replace("postgresql://", "postgresql+psycopg://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = raw_db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODELS ---
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

# --- INITIALIZE DATABASE AND CREATE DEFAULT ADMIN ---
with app.app_context():
    db.create_all()
    if not Admin.query.filter_by(username="admin").first():
        admin = Admin(username="admin", password="password")
        db.session.add(admin)
        db.session.commit()

# --- ROUTES ---
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
        password = request.form.get('password
