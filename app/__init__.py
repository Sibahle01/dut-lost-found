from flask import Flask, redirect, url_for, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from config import Config

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
csrf = CSRFProtect()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)

    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'

    # Import models
    from app.models import user, item, claim, match, notification

    # Create database tables
    with app.app_context():
        db.create_all()
        print("✅ Database tables created successfully")

    # Register blueprints
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.items import bp as items_bp
    app.register_blueprint(items_bp, url_prefix='/items')

    from app.claims import bp as claims_bp
    app.register_blueprint(claims_bp, url_prefix='/claims')

    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    from app.notifications import bp as notifications_bp
    app.register_blueprint(notifications_bp, url_prefix='/notifications')

    from app.matching import bp as matching_bp
    app.register_blueprint(matching_bp, url_prefix='/matching')

    # ── Home route ────────────────────────────────────────────────────────
    @app.route('/')
    def home():
        from app.models.item import Item
        from sqlalchemy import or_

        # Show open AND matched lost items so the homepage stays populated
        # even after admin matching activity
        recent_lost = Item.query.filter(
            Item.type == 'lost',
            or_(Item.status == 'open', Item.status == 'matched')
        ).order_by(Item.created_at.desc()).limit(6).all()

        # Found items — open and matched
        recent_found = Item.query.filter(
            Item.type == 'found',
            or_(Item.status == 'open', Item.status == 'matched')
        ).order_by(Item.created_at.desc()).limit(6).all()

        return render_template('index.html',
                               recent_lost=recent_lost,
                               recent_found=recent_found)

    @app.route('/test-db')
    def test_db():
        try:
            from app.models.user import User
            user_count = User.query.count()
            return f'✅ Database connection successful! User count: {user_count}'
        except Exception as e:
            return f'❌ Database error: {str(e)}'

    return app


# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    from app.models.user import User
    return User.query.get(int(user_id))