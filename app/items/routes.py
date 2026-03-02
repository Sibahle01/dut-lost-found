from flask import render_template
from flask_login import login_required, current_user
from app.items import bp

@bp.route('/')
def index():
    return render_template('items/index.html')

@bp.route('/search')
def search():
    return render_template('items/search.html')

@bp.route('/report')
@login_required
def report():
    return render_template('items/report.html')
