from flask import render_template
from flask_login import login_required, current_user
from app.notifications import bp

@bp.route('/')
@login_required
def index():
    return render_template('notifications/index.html')

@bp.route('/api/count')
@login_required
def count():
    # Placeholder for notifications count
    return {"count": 0}
