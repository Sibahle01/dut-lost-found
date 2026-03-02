from flask import render_template
from flask_login import login_required, current_user
from app.claims import bp

@bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('claims/dashboard.html', user=current_user)

# This route will be implemented by the claims team
@bp.route('/submit/<int:item_id>', methods=['GET', 'POST'])
@login_required
def submit(item_id):
    # Placeholder - will be implemented by claims team
    return f"Claim submission for item {item_id} - Coming soon"
