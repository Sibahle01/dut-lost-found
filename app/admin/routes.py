from flask import render_template
from flask_login import login_required, current_user
from app.admin import bp

@bp.route('/dashboard')
@login_required
def dashboard():
    # Check if user is admin
    if not current_user.is_admin:
        return "Access denied - Admins only", 403
    return render_template('admin/dashboard.html')

# Additional placeholder routes for admin team
@bp.route('/claims')
@login_required
def claims_list():
    if not current_user.is_admin:
        return "Access denied - Admins only", 403
    return "Admin claims management - Coming soon"

@bp.route('/claims/<int:claim_id>/review', methods=['GET', 'POST'])
@login_required
def review_claim(claim_id):
    if not current_user.is_admin:
        return "Access denied - Admins only", 403
    return f"Review claim #{claim_id} - Coming soon"
