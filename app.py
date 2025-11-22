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

# --- DATABASE CONFIG - Compatible approach ---
raw_db_url = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost/euromove"  # Use simple postgresql://
)

# Fix Heroku-style URLs
if raw_db_url and raw_db_url.startswith("postgres://"):
    raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)

print(f"🔧 Using database URL: {raw_db_url.split('@')[0]}@...")

# Configure Flask-SQLAlchemy
app.config["SQLALCHEMY_DATABASE_URI"] = raw_db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

# Initialize db without forcing psycopg3 in the URL
db = SQLAlchemy(app)

# --- MODELS ---
class Workshop(db.Model):
    __tablename__ = 'workshop'
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
    __tablename__ = 'post'
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
    __tablename__ = 'booking'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

class Admin(db.Model):
    __tablename__ = 'admin'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(50))
    whatsapp_number = db.Column(db.String(20), default="+1234567890")
    email_address = db.Column(db.String(100), default="admin@example.com")

# --- INITIALIZE DATABASE ---
with app.app_context():
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
        print(f"❌ Database initialization error: {e}")

# --- ROUTES ---
@app.route('/')
def index():
    try:
        latest_post = Post.query.order_by(Post.date_posted.desc()).first()
        upcoming_workshops = Workshop.query.order_by(Workshop.date_posted.desc()).limit(3).all()
        admin = Admin.query.first()
    except Exception as e:
        print(f"Database query error: {e}")
        latest_post = None
        upcoming_workshops = []
        admin = None
    
    return render_template('index.html', 
                         latest_post=latest_post, 
                         upcoming_workshops=upcoming_workshops,
                         admin=admin,
                         datetime=datetime)

@app.route('/posts')
def posts():
    try:
        all_posts = Post.query.order_by(Post.date_posted.desc()).all()
    except Exception as e:
        print(f"Posts query error: {e}")
        all_posts = []
    return render_template('posts.html', posts=all_posts, datetime=datetime)

@app.route('/workshops')
def workshops():
    try:
        all_workshops = Workshop.query.order_by(Workshop.date_posted.desc()).all()
    except Exception as e:
        print(f"Workshops query error: {e}")
        all_workshops = []
    return render_template('workshops.html', workshops=all_workshops, datetime=datetime)

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

@app.route('/gallery')
def gallery():
    return render_template('gallery.html', datetime=datetime)

@app.route('/privacy')
def privacy():
    admin = Admin.query.first()
    return render_template('privacy.html', admin=admin, datetime=datetime)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        try:
            admin = Admin.query.filter_by(username=username, password=password).first()
            if admin:
                session['admin_logged_in'] = True
                return redirect(url_for('admin_dashboard'))
            else:
                flash("Invalid username or password", "danger")
        except Exception as e:
            flash("Database error during login", "danger")
    return render_template('admin_login.html')

@app.route('/admin/dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    try:
        admin = Admin.query.first()
        posts = Post.query.order_by(Post.date_posted.desc()).all()
        workshops = Workshop.query.order_by(Workshop.date_posted.desc()).all()
        bookings = Booking.query.order_by(Booking.created_at.desc()).all()
    except Exception as e:
        print(f"Admin dashboard query error: {e}")
        admin = None
        posts = []
        workshops = []
        bookings = []

    if request.method == 'POST':
        try:
            if 'whatsapp_number' in request.form:
                admin.whatsapp_number = request.form.get('whatsapp_number', '').strip()
                admin.email_address = request.form.get('email_address', '').strip()
                db.session.commit()
                flash("Contact information updated successfully", "success")
            elif 'post_title' in request.form:
                title = request.form.get('post_title', '').strip()
                content = request.form.get('post_content', '').strip()
                content_format = request.form.get('post_format', 'html')
                image_url = request.form.get('post_image', '').strip() or None

                if not title or not content:
                    flash("Post title and content are required", "danger")
                else:
                    post = Post(
                        title=title, 
                        content=content, 
                        content_format=content_format,
                        image_url=image_url
                    )
                    db.session.add(post)
                    db.session.commit()
                    flash("Post added successfully", "success")
            elif 'workshop_title' in request.form:
                title = request.form.get('workshop_title', '').strip()
                description = request.form.get('workshop_content', '').strip()
                content_format = request.form.get('workshop_format', 'html')
                image_url = request.form.get('workshop_image', '').strip() or None

                if not title or not description:
                    flash("Workshop title and description are required", "danger")
                else:
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
            flash(f"Error: {e}", "danger")

    return render_template('admin_dashboard.html', 
                         posts=posts, 
                         workshops=workshops, 
                         bookings=bookings,
                         admin=admin,
                         datetime=datetime)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

if __name__ == '__main__':
    app.run(debug=True)