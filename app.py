from dotenv import load_dotenv
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, Response  # Added Response
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

# Site configuration
SITE_URL = "https://euromove.co.ke"  # Your site URL

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


# --- Helper Functions ---
def create_slug(text):
    """Create a URL-friendly slug from text"""
    # Convert to lowercase
    text = text.lower()
    # Replace spaces with hyphens
    text = text.replace(' ', '-')
    # Remove special characters, keep only alphanumeric and hyphens
    text = re.sub(r'[^a-z0-9\-]', '', text)
    # Remove multiple hyphens
    text = re.sub(r'\-+', '-', text)
    # Remove leading/trailing hyphens
    text = text.strip('-')
    return text


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

class SiteSettings(db.Model):
    __tablename__ = 'site_settings'
    id = db.Column(db.Integer, primary_key=True)
    logo_url = db.Column(db.String(500), nullable=True)          # allow nullable to prevent INSERT errors
    background_url = db.Column(db.String(500), nullable=True)    # allow nullable
    created_at = db.Column(db.DateTime, default=datetime.now) # safe per-row timestamp

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.String(50), nullable=False)  # e.g., "2 500 KES"
    content_format = db.Column(db.String(10), default='html')
    action_type = db.Column(db.String(20), default='book')  # 'book' or 'view'
    action_link = db.Column(db.String(300), nullable=True)  # optional for 'view course'
    created_at = db.Column(db.DateTime, default=datetime.now)
    is_active = db.Column(db.Boolean, default=True)
    
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


# --- CONTEXT PROCESSOR: Inject site settings into all templates ---
@app.context_processor
def inject_site_settings():
    setting = SiteSettings.query.first()
    return dict(site_settings=setting)


# --- ROBOTS.TXT ROUTE ---
@app.route('/robots.txt')
def robots_txt():
    """Serve robots.txt for SEO optimization for euromove.co.ke"""
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /private/",
        "Disallow: /tmp/",
        f"Sitemap: {SITE_URL}/sitemap.xml",
        f"Sitemap: {SITE_URL}/sitemap-posts.xml",
        f"Sitemap: {SITE_URL}/sitemap-workshops.xml",
        "",
        "# Googlebot specific",
        "User-agent: Googlebot",
        "Allow: /",
        "Disallow: /admin/",
        "Crawl-delay: 1",
        "",
        "# Bingbot",
        "User-agent: Bingbot",
        "Allow: /",
        "Disallow: /admin/",
        "Crawl-delay: 2",
        "",
        "# Bad bots",
        "User-agent: MJ12bot",
        "Disallow: /",
        "",
        "User-agent: AhrefsBot",
        "Disallow: /",
        "",
        "# Site contact",
        f"# Site: {SITE_URL}",
        "# Contact: admin@euromove.co.ke",
    ]
    return Response("\n".join(lines), mimetype="text/plain")


# --- SITEMAP.XML ROUTE ---
@app.route('/sitemap.xml')
def sitemap():
    """Generate dynamic sitemap.xml for euromove.co.ke"""
    
    # Get all posts and workshops
    posts = Post.query.order_by(Post.date_posted.desc()).all()
    workshops = Workshop.query.order_by(Workshop.date_posted.desc()).all()
    
    # Start XML
    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        '  <sitemap>',
        f'    <loc>{SITE_URL}/sitemap-posts.xml</loc>',
        '    <lastmod>' + datetime.now().strftime("%Y-%m-%d") + '</lastmod>',
        '  </sitemap>',
        '  <sitemap>',
        f'    <loc>{SITE_URL}/sitemap-workshops.xml</loc>',
        '    <lastmod>' + datetime.now().strftime("%Y-%m-%d") + '</lastmod>',
        '  </sitemap>',
        '  <sitemap>',
        f'    <loc>{SITE_URL}/sitemap-static.xml</loc>',
        '    <lastmod>' + datetime.now().strftime("%Y-%m-%d") + '</lastmod>',
        '  </sitemap>',
        '</sitemapindex>'
    ]
    
    return Response("\n".join(xml_lines), mimetype="application/xml")


# --- SITEMAP-POSTS.XML ---
@app.route('/sitemap-posts.xml')
def sitemap_posts():
    """Sitemap for all blog posts"""
    posts = Post.query.order_by(Post.date_posted.desc()).all()
    
    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    
    for post in posts:
        slug = create_slug(post.title)
        xml_lines.extend([
            '  <url>',
            f'    <loc>{SITE_URL}/posts/{slug}</loc>',
            f'    <lastmod>{post.date_posted.strftime("%Y-%m-%d")}</lastmod>',
            '    <changefreq>monthly</changefreq>',
            '    <priority>0.8</priority>',
            '  </url>',
        ])
    
    xml_lines.append('</urlset>')
    return Response("\n".join(xml_lines), mimetype="application/xml")


# --- SITEMAP-WORKSHOPS.XML ---
@app.route('/sitemap-workshops.xml')
def sitemap_workshops():
    """Sitemap for all workshops"""
    workshops = Workshop.query.order_by(Workshop.date_posted.desc()).all()
    
    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    
    # Add workshops page
    xml_lines.extend([
        '  <url>',
        f'    <loc>{SITE_URL}/workshops</loc>',
        '    <lastmod>' + datetime.now().strftime("%Y-%m-d") + '</lastmod>',
        '    <changefreq>weekly</changefreq>',
        '    <priority>0.9</priority>',
        '  </url>',
    ])
    
    xml_lines.append('</urlset>')
    return Response("\n".join(xml_lines), mimetype="application/xml")


# --- SITEMAP-STATIC.XML ---
@app.route('/sitemap-static.xml')
def sitemap_static():
    """Sitemap for static pages"""
    
    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    
    # Add all static pages
    static_pages = [
        ('', '1.0', 'daily'),
        ('/posts', '0.9', 'weekly'),
        ('/workshops', '0.9', 'weekly'),
        ('/services', '0.9', 'weekly'),
        ('/gallery', '0.8', 'weekly'),
        ('/privacy', '0.3', 'monthly'),
    ]
    
    for page, priority, changefreq in static_pages:
        xml_lines.extend([
            '  <url>',
            f'    <loc>{SITE_URL}{page}</loc>',
            '    <lastmod>' + datetime.now().strftime("%Y-%m-%d") + '</lastmod>',
            f'    <changefreq>{changefreq}</changefreq>',
            f'    <priority>{priority}</priority>',
            '  </url>',
        ])
    
    xml_lines.append('</urlset>')
    return Response("\n".join(xml_lines), mimetype="application/xml")


# --- ALL ROUTES WITH COMPLETE FUNCTIONALITY ---
# Public home page
@app.route('/')
def index():
    # Get latest post for dynamic content
    latest_post = Post.query.order_by(Post.date_posted.desc()).first()
    # Get upcoming workshops (next 7 days)
    upcoming_workshops = Workshop.query.order_by(Workshop.date_posted.desc()).limit(3).all()
    # Get active services for home page
    services = Service.query.filter_by(is_active=True).order_by(Service.created_at.asc()).limit(3).all()
    # Get admin contact info
    admin = Admin.query.first()
    
    return render_template('index.html', 
                         latest_post=latest_post, 
                         upcoming_workshops=upcoming_workshops,
                         services=services,
                         admin=admin,
                         datetime=datetime,
                         SITE_URL=SITE_URL)


# Individual post page
@app.route('/posts/<slug>')
def post_detail(slug):
    # Find post by matching cleaned slug
    all_posts = Post.query.all()
    for post in all_posts:
        post_slug = create_slug(post.title)
        if post_slug == slug:
            return render_template('post_detail.html', post=post, SITE_URL=SITE_URL)
    
    # If not found by slug, try direct title match (backward compatibility)
    title = slug.replace('-', ' ')
    post = Post.query.filter_by(title=title).first()
    if post:
        return render_template('post_detail.html', post=post, SITE_URL=SITE_URL)
    
    # Return 404 if not found
    from flask import abort
    abort(404)


# All posts listing
@app.route('/posts')
def posts():
    all_posts = Post.query.order_by(Post.date_posted.desc()).all()
    return render_template('posts.html', posts=all_posts, datetime=datetime, SITE_URL=SITE_URL)


# Services page
@app.route('/services')
def services():
    all_services = Service.query.filter_by(is_active=True).order_by(Service.created_at.asc()).all()
    admin = Admin.query.first()
    return render_template('services.html', 
                         services=all_services, 
                         admin=admin,
                         datetime=datetime,
                         SITE_URL=SITE_URL)


# Book a specific service
@app.route('/book/service/<int:service_id>', methods=['GET', 'POST'])
def book_service(service_id):
    service = Service.query.get_or_404(service_id)
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        
        if name and email and phone:
            try:
                booking = Booking(name=name, email=email, phone=phone)
                db.session.add(booking)
                db.session.commit()
                flash(f'Thank you {name}, your booking for "{service.title}" has been received! We will contact you soon.', 'success')
                return redirect(url_for('services'))
            except Exception as e:
                db.session.rollback()
                flash('Sorry, there was an error processing your booking. Please try again.', 'danger')
        else:
            flash('Please fill in all fields.', 'danger')
    
    return render_template('book_service.html', service=service, SITE_URL=SITE_URL)


# Workshops page
@app.route('/workshops')
def workshops():
    all_workshops = Workshop.query.order_by(Workshop.date_posted.desc()).all()

    # Ensure each workshop has a slug for internal linking
    for workshop in all_workshops:
        if not hasattr(workshop, 'slug') or not workshop.slug:
            workshop.slug = workshop.title.replace(" ", "_")  # simple slug

    return render_template('workshops.html', workshops=all_workshops, datetime=datetime, SITE_URL=SITE_URL)


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


#gallery
@app.route('/gallery')
def gallery():
    try:
        # Wrap query string in text() inline
        rows = db.session.execute(db.text("""
            SELECT item_id, source, image_url, title, created_at
            FROM gallery
            WHERE image_url IS NOT NULL AND image_url != 'No image'
            ORDER BY created_at DESC
        """)).fetchall()

        # Convert to list of dicts
        gallery_data = []
        for r in rows:
            gallery_data.append({
                "item_id": r.item_id,
                "source": r.source,
                "image_url": r.image_url,
                "title": r.title,
                "created_at": r.created_at
            })

        # Pass to template
        return render_template('gallery.html', gallery=gallery_data, datetime=datetime, SITE_URL=SITE_URL)

    except Exception as e:
        print("Error fetching gallery:", e)
        return "Internal Server Error", 500


# Privacy Policy route
@app.route('/privacy')
def privacy():
    admin = Admin.query.first()
    return render_template('privacy.html', admin=admin, datetime=datetime, SITE_URL=SITE_URL)


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
    return render_template('admin_login.html', SITE_URL=SITE_URL)


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

        # Add Service
        elif 'service_title' in request.form:
            title = request.form.get('service_title', '').strip()
            description = request.form.get('service_description', '').strip()
            price = request.form.get('service_price', '').strip()
            content_format = request.form.get('service_format', 'html')
            action_type = request.form.get('service_action_type', 'book')
            action_link = request.form.get('service_action_link', '').strip() or None
            
            if not title or not description or not price:
                flash("Service title, description, and price are required", "danger")
            else:
                try:
                    service = Service(
                        title=title,
                        description=description,
                        price=price,
                        content_format=content_format,
                        action_type=action_type,
                        action_link=action_link
                    )
                    db.session.add(service)
                    db.session.commit()
                    flash("Service added successfully", "success")
                except Exception as e:
                    db.session.rollback()
                    flash(f"Error adding service: {e}", "danger")

         # --- Site Settings Logic ---
        if request.method == 'POST':
            # --- Update Site Settings ---
            if request.form.get('form_type') == 'update_site_settings':
                logo_url = request.form.get('logo_url', '').strip()
                background_url = request.form.get('background_url', '').strip()

                if not logo_url or not background_url:
                    flash("Both Logo URL and Background Image URL are required", "danger")
                else:
                    try:
                        setting = SiteSettings.query.first()
                        if not setting:
                            setting = SiteSettings(logo_url=logo_url, background_url=background_url)
                            db.session.add(setting)
                        else:
                            setting.logo_url = logo_url
                            setting.background_url = background_url
                        db.session.commit()
                        flash("Site settings updated successfully", "success")
                    except Exception as e:
                        db.session.rollback()
                        flash(f"Error updating site settings: {e}", "danger")

            # --- Delete Site Settings ---
            elif request.form.get('form_type') == 'delete_site_settings':
                try:
                    setting = SiteSettings.query.first()
                    if setting:
                        db.session.delete(setting)
                        db.session.commit()
                        flash("Site settings deleted successfully", "success")
                    else:
                        flash("No site settings found to delete", "danger")
                except Exception as e:
                    db.session.rollback()
                    flash(f"Error deleting site settings: {e}", "danger")

    # Fetch all data for dashboard
    posts = Post.query.order_by(Post.date_posted.desc()).all()
    workshops = Workshop.query.order_by(Workshop.date_posted.desc()).all()
    services = Service.query.order_by(Service.created_at.desc()).all()
    bookings = Booking.query.order_by(Booking.created_at.desc()).all()
    site_settings = SiteSettings.query.first()
    return render_template('admin_dashboard.html', 
                         posts=posts, 
                         workshops=workshops, 
                         services=services,
                         bookings=bookings,
                         admin=admin,
                         site_settings=site_settings,
                         datetime=datetime,
                         SITE_URL=SITE_URL)


# --- ADMIN SERVICE MANAGEMENT ---
@app.route('/admin/service/edit/<int:service_id>', methods=['GET', 'POST'])
def edit_service(service_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    service = Service.query.get_or_404(service_id)
    
    if request.method == 'POST':
        service.title = request.form.get('service_title', '').strip()
        service.description = request.form.get('service_description', '').strip()
        service.price = request.form.get('service_price', '').strip()
        service.content_format = request.form.get('service_format', 'html')
        service.action_type = request.form.get('service_action_type', 'book')
        service.action_link = request.form.get('service_action_link', '').strip() or None
        service.is_active = 'service_is_active' in request.form
        
        if not service.title or not service.description or not service.price:
            flash("Title, description, and price are required", "danger")
        else:
            try:
                db.session.commit()
                flash("Service updated successfully", "success")
                return redirect(url_for('admin_dashboard'))
            except Exception as e:
                db.session.rollback()
                flash(f"Error updating service: {e}", "danger")
    
    return render_template('edit_service.html', service=service, SITE_URL=SITE_URL)


@app.route('/admin/service/delete/<int:service_id>', methods=['POST'])
def delete_service(service_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    service = Service.query.get_or_404(service_id)
    
    try:
        db.session.delete(service)
        db.session.commit()
        flash(f'Service "{service.title}" deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting service: {e}', 'danger')
    
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/service/toggle/<int:service_id>', methods=['POST'])
def toggle_service(service_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    service = Service.query.get_or_404(service_id)
    service.is_active = not service.is_active
    
    try:
        db.session.commit()
        status = "activated" if service.is_active else "deactivated"
        flash(f'Service "{service.title}" {status} successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating service: {e}', 'danger')
    
    return redirect(url_for('admin_dashboard'))


# --- LOGOUT ---
@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))


# --- RUN APP ---
if __name__ == '__main__':
    app.run(debug=True)