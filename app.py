from dotenv import load_dotenv
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import markdown
import bleach
import time
import re
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

# --- Load environment variables ---
load_dotenv()

# --- Initialize Flask app ---
app = Flask(__name__)
app.secret_key = "supersecretkey"

# --- DATABASE CONFIG WITH SSL & CONNECTION POOLING ---
raw_db_url = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:password@localhost/euromove"
)

# Fix Heroku-style URLs
if raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql+psycopg://", 1)

# Enforce SSL (Supabase/Render)
if "sslmode" not in raw_db_url:
    separator = "&" if "?" in raw_db_url else "?"
    raw_db_url += f"{separator}sslmode=require"

app.config['SQLALCHEMY_DATABASE_URI'] = raw_db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'pool_size': 5,
    'max_overflow': 10,
    # psycopg3 uses sslmode directly; keepalives supported via connect_args
    'connect_args': {
        'sslmode': 'require'
    }
}

db = SQLAlchemy(app)


# --- DATABASE WAKE-UP LOGIC FOR RENDER ---
def wake_up_database():
    """Wait for database to become available (Render cold start issue)"""
    max_retries = 10
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            with app.app_context():
                db.session.execute(text("SELECT 1"))
                print("✅ Database is awake and responsive")
                return True
        except OperationalError as e:
            if attempt < max_retries - 1:
                print(f"⏳ Database not ready yet (attempt {attempt + 1}/{max_retries}), retrying in {retry_delay}s...")
                time.sleep(retry_delay)
            else:
                print(f"❌ Database failed to wake up after {max_retries} attempts: {e}")
                return False
        except Exception as e:
            print(f"❌ Unexpected error during database wake-up: {e}")
            return False

# --- MODELS ---
class Workshop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150))
    description = db.Column(db.Text)
    content_format = db.Column(db.String(10), default='html')
    image_url = db.Column(db.String(300))
    date_posted = db.Column(db.DateTime, default=datetime.now)
    
    def rendered_content(self):
        if self.content_format == 'markdown':
            html = markdown.markdown(self.description, extensions=['extra', 'fenced_code'])
            return self.sanitize_html(html)
        return self.sanitize_html(self.description)
    
    def sanitize_html(self, html_content):
        allowed_tags = ['p', 'br', 'strong', 'em', 'u', 'b', 'i', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 
                       'ul', 'ol', 'li', 'a', 'img', 'blockquote', 'code', 'pre', 'span', 'div']
        allowed_attrs = {
            'a': ['href', 'title', 'target'],
            'img': ['src', 'alt', 'width', 'height', 'class'],
            'div': ['class'],
            'span': ['class']
        }
        return bleach.clean(html_content, tags=allowed_tags, attributes=allowed_attrs)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text)
    content_format = db.Column(db.String(10), default='html', nullable=False)
    image_url = db.Column(db.String(300))
    date_posted = db.Column(db.DateTime, default=datetime.now)
    
    def rendered_content(self):
        if self.content_format == 'markdown':
            html = markdown.markdown(self.content, extensions=['extra', 'fenced_code'])
            return self.sanitize_html(html)
        return self.sanitize_html(self.content)
    
    def sanitize_html(self, html_content):
        allowed_tags = ['p', 'br', 'strong', 'em', 'u', 'b', 'i', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 
                       'ul', 'ol', 'li', 'a', 'img', 'blockquote', 'code', 'pre', 'span', 'div']
        allowed_attrs = {
            'a': ['href', 'title', 'target'],
            'img': ['src', 'alt', 'width', 'height', 'class'],
            'div': ['class'],
            'span': ['class']
        }
        return bleach.clean(html_content, tags=allowed_tags, attributes=allowed_attrs)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(50))
    whatsapp_number = db.Column(db.String(20), default="+1234567890")
    email_address = db.Column(db.String(100), default="admin@example.com")

# --- INITIALIZE DATABASE WITH WAKE-UP ---
with app.app_context():
    # Wake up database first
    if wake_up_database():
        try:
            db.create_all()
            if not Admin.query.filter_by(username="admin").first():
                admin = Admin(
                    username="admin", 
                    password="password",
                    whatsapp_number="+1234567890",
                    email_address="admin@example.com"
                )
                db.session.add(admin)
                db.session.commit()
                print("✅ Database and default admin created successfully")
        except Exception as e:
            print(f"❌ Database initialization failed: {e}")
    else:
        print("⚠️  Database not available, skipping initialization")

# --- ALL ROUTES WITH COMPLETE FUNCTIONALITY ---

# Public home page
@app.route('/')
def index():
    # Get latest post for dynamic content
    latest_post = Post.query.order_by(Post.date_posted.desc()).first()
    # Get upcoming workshops (next 7 days)
    upcoming_workshops = Workshop.query.order_by(Workshop.date_posted.desc()).limit(3).all()
    # Get admin contact info
    admin = Admin.query.first()
    
    return render_template('index.html', 
                         latest_post=latest_post, 
                         upcoming_workshops=upcoming_workshops,
                         admin=admin,
                         datetime=datetime)


# Individual post page
@app.route('/posts/<int:post_id>')
def post_detail(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template('post_detail.html', post=post)

# All posts listing
@app.route('/posts')
def posts():
    all_posts = Post.query.order_by(Post.date_posted.desc()).all()
    return render_template('posts.html', posts=all_posts, datetime=datetime)

# Workshops page
@app.route('/workshops')
def workshops():
    all_workshops = Workshop.query.order_by(Workshop.date_posted.desc()).all()

    # Ensure each workshop has a slug for internal linking
    for workshop in all_workshops:
        if not hasattr(workshop, 'slug') or not workshop.slug:
            workshop.slug = workshop.title.replace(" ", "_")  # simple slug

    return render_template('workshops.html', workshops=all_workshops, datetime=datetime)



# Booking route
@app.route('/book', methods=['POST'])
def book():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    
    if name and email and phone:
        try:
            booking = Booking(name=name, email=email, phone=phone)
            db.session.add(booking)
            db.session.commit()
            flash(f'Thank you {name}, your slot has been booked! We will contact you soon.', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Sorry, there was an error processing your booking. Please try again.', 'danger')
    else:
        flash('Please fill in all fields.', 'danger')
    
    return redirect(url_for('index'))

# Gallery route
@app.route('/gallery')
def gallery():
    return render_template('gallery.html', datetime=datetime)

# Privacy Policy route
@app.route('/privacy')
def privacy():
    admin = Admin.query.first()
    return render_template('privacy.html', admin=admin, datetime=datetime)

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

    admin = Admin.query.first()

    if request.method == 'POST':
        # Update contact info
        if 'whatsapp_number' in request.form:
            admin.whatsapp_number = request.form.get('whatsapp_number', '').strip()
            admin.email_address = request.form.get('email_address', '').strip()
            db.session.commit()
            flash("Contact information updated successfully", "success")

        # Add Post
        elif 'post_title' in request.form:
            title = request.form.get('post_title', '').strip()
            content = request.form.get('post_content', '').strip()
            content_format = request.form.get('post_format', 'html')
            image_url = request.form.get('post_image', '').strip() or None

            if not title or not content:
                flash("Post title and content are required", "danger")
            else:
                try:
                    post = Post(
                        title=title, 
                        content=content, 
                        content_format=content_format,
                        image_url=image_url
                    )
                    db.session.add(post)
                    db.session.commit()
                    flash("Post added successfully", "success")
                except Exception as e:
                    db.session.rollback()
                    flash(f"Error adding post: {e}", "danger")

        # Add Workshop
        elif 'workshop_title' in request.form:
            title = request.form.get('workshop_title', '').strip()
            description = request.form.get('workshop_content', '').strip()
            content_format = request.form.get('workshop_format', 'html')
            image_url = request.form.get('workshop_image', '').strip() or None

            if not title or not description:
                flash("Workshop title and description are required", "danger")
            else:
                try:
                    ws = Workshop(
                        title=title, 
                        description=description,
                        content_format=content_format,
                        image_url=image_url
                    )
                    db.session.add(ws)
                    db.session.commit()
                    flash("Workshop added successfully", "success")
                except Exception as e:
                    db.session.rollback()
                    flash(f"Error adding workshop: {e}", "danger")

    # Fetch all data for dashboard
    posts = Post.query.order_by(Post.date_posted.desc()).all()
    workshops = Workshop.query.order_by(Workshop.date_posted.desc()).all()
    bookings = Booking.query.order_by(Booking.created_at.desc()).all()

    return render_template('admin_dashboard.html', 
                         posts=posts, 
                         workshops=workshops, 
                         bookings=bookings,
                         admin=admin,
                         datetime=datetime)

# --- LOGOUT ---
@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

# --- RUN APP ---
if __name__ == '__main__':
    app.run(debug=True)