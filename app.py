from dotenv import load_dotenv
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import markdown
import bleach

# --- Load environment variables ---
load_dotenv()

# --- Initialize Flask app ---
app = Flask(__name__)
app.secret_key = "supersecretkey"

# --- DATABASE CONFIG ---
raw_db_url = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost/euromove"
)

# Fix Supabase URLs for SQLAlchemy + psycopg (Render compatible)
if raw_db_url and raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)

# Apply to Flask app
app.config['SQLALCHEMY_DATABASE_URI'] = raw_db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODELS ---
class Workshop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150))
    description = db.Column(db.Text)
    content_format = db.Column(db.String(10), default='html')  # 'html' or 'markdown'
    image_url = db.Column(db.String(300))
    date_posted = db.Column(db.DateTime, default=datetime.now)
    
    def rendered_content(self):
        """Convert content to HTML based on format"""
        if self.content_format == 'markdown':
            html = markdown.markdown(self.description, extensions=['extra', 'fenced_code'])
            return self.sanitize_html(html)
        return self.sanitize_html(self.description)
    
    def sanitize_html(self, html_content):
        """Sanitize HTML to prevent XSS attacks"""
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
    title = db.Column(db.String(150))
    content = db.Column(db.Text)
    content_format = db.Column(db.String(10), default='html')  # 'html' or 'markdown'
    image_url = db.Column(db.String(300))
    date_posted = db.Column(db.DateTime, default=datetime.now)
    
    def rendered_content(self):
        """Convert content to HTML based on format"""
        if self.content_format == 'markdown':
            html = markdown.markdown(self.content, extensions=['extra', 'fenced_code'])
            return self.sanitize_html(html)
        return self.sanitize_html(self.content)
    
    def sanitize_html(self, html_content):
        """Sanitize HTML to prevent XSS attacks"""
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

# --- INITIALIZE DATABASE AND DEFAULT ADMIN ---
with app.app_context():
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

# --- ROUTES ---

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

# Posts page
@app.route('/posts')
def posts():
    all_posts = Post.query.order_by(Post.date_posted.desc()).all()
    return render_template('posts.html', posts=all_posts, datetime=datetime)

# Workshops page
@app.route('/workshops')
def workshops():
    all_workshops = Workshop.query.order_by(Workshop.date_posted.desc()).all()
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