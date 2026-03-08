from datetime import datetime
from functools import wraps
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.admin import bp
from app import db
from app.models.user import User
from app.models.item import Item
from app.models.claim import Claim
from app.models.match import Match
from app.models.notification import Notification


# ── ADMIN GUARD ───────────────────────────────────────────────────────────────
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Access denied. Admins only.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


# ── DASHBOARD ─────────────────────────────────────────────────────────────────
@bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    stats = {
        'pending_claims'  : Claim.query.filter_by(status='pending').count(),
        'total_items'     : Item.query.count(),
        'open_items'      : Item.query.filter_by(status='open').count(),
        'total_users'     : User.query.filter_by(role='student').count(),
        'approved_claims' : Claim.query.filter_by(status='approved').count(),
        'closed_items'    : Item.query.filter_by(status='closed').count(),
    }
    recent_claims = Claim.query.order_by(Claim.created_at.desc()).limit(10).all()
    recent_items  = Item.query.order_by(Item.created_at.desc()).limit(10).all()
    unread_count  = Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).count()

    return render_template('admin/dashboard.html',
                           stats=stats,
                           recent_claims=recent_claims,
                           recent_items=recent_items,
                           unread_count=unread_count)


# ── CLAIMS LIST ───────────────────────────────────────────────────────────────
@bp.route('/claims')
@login_required
@admin_required
def claims_list():
    status_filter = request.args.get('status', 'pending')
    valid_statuses = ['pending', 'approved', 'rejected', 'all']

    if status_filter not in valid_statuses:
        status_filter = 'pending'

    if status_filter == 'all':
        claims = Claim.query.order_by(Claim.created_at.desc()).all()
    else:
        claims = Claim.query.filter_by(status=status_filter)\
                            .order_by(Claim.created_at.desc()).all()

    counts = {
        'pending'  : Claim.query.filter_by(status='pending').count(),
        'approved' : Claim.query.filter_by(status='approved').count(),
        'rejected' : Claim.query.filter_by(status='rejected').count(),
    }

    return render_template('admin/claims_list.html',
                           claims=claims,
                           status_filter=status_filter,
                           counts=counts)


# ── REVIEW CLAIM ──────────────────────────────────────────────────────────────
@bp.route('/claims/<int:claim_id>/review', methods=['GET', 'POST'])
@login_required
@admin_required
def review_claim(claim_id):
    claim = Claim.query.get_or_404(claim_id)
    item  = Item.query.get_or_404(claim.item_id)
    claimant = User.query.get_or_404(claim.claimant_id)

    if request.method == 'POST':
        decision = request.form.get('decision')
        rejection_reason = request.form.get('rejection_reason', '').strip()

        if decision not in ['approve', 'reject']:
            flash('Invalid decision.', 'danger')
            return redirect(url_for('admin.review_claim', claim_id=claim_id))

        if decision == 'reject' and not rejection_reason:
            flash('A rejection reason is required.', 'danger')
            return redirect(url_for('admin.review_claim', claim_id=claim_id))

        # ── Apply Decision ────────────────────────────────────────────────
        claim.reviewed_by  = current_user.id
        claim.reviewed_at  = datetime.utcnow()

        if decision == 'approve':
            claim.status  = 'approved'
            item.status   = 'claimed'

            # Notify claimant
            db.session.add(Notification(
                user_id=claimant.id,
                related_item_id=item.id,
                type='claim_approved',
                message=f'Your claim for "{item.title}" ({item.reference_number}) '
                        f'has been approved. Visit {item.campus} campus with your '
                        f'student card to collect your item.',
                channel='in_app'
            ))
            # Notify finder
            db.session.add(Notification(
                user_id=item.reported_by,
                related_item_id=item.id,
                type='item_closed',
                message=f'The item you reported ("{item.title}", '
                        f'{item.reference_number}) has been claimed and '
                        f'is ready for handover.',
                channel='in_app'
            ))
            flash(f'Claim approved. {claimant.name} has been notified to '
                  f'collect the item.', 'success')

        else:
            claim.status          = 'rejected'
            claim.rejection_reason = rejection_reason

            db.session.add(Notification(
                user_id=claimant.id,
                related_item_id=item.id,
                type='claim_rejected',
                message=f'Your claim for "{item.title}" ({item.reference_number}) '
                        f'was not approved. Reason: {rejection_reason}',
                channel='in_app'
            ))
            flash(f'Claim rejected. {claimant.name} has been notified.', 'warning')

        db.session.commit()
        return redirect(url_for('admin.claims_list'))

    # GET — show the review page
    # private_verification is shown HERE and ONLY here
    return render_template('admin/review_claim.html',
                           claim=claim,
                           item=item,
                           claimant=claimant)


# ── LOG HANDOVER ──────────────────────────────────────────────────────────────
@bp.route('/claims/<int:claim_id>/handover', methods=['POST'])
@login_required
@admin_required
def log_handover(claim_id):
    claim = Claim.query.get_or_404(claim_id)
    item  = Item.query.get_or_404(claim.item_id)

    if claim.status != 'approved':
        flash('Only approved claims can be handed over.', 'danger')
        return redirect(url_for('admin.claims_list'))

    student_number = request.form.get('student_number', '').strip()
    if not student_number:
        flash('Student number is required to log handover.', 'danger')
        return redirect(url_for('admin.review_claim', claim_id=claim_id))

    claim.handover_logged_at      = datetime.utcnow()
    claim.handover_student_number = student_number
    item.status = 'closed'

    db.session.add(Notification(
        user_id=item.reported_by,
        related_item_id=item.id,
        type='item_closed',
        message=f'Item "{item.title}" ({item.reference_number}) has been '
                f'successfully handed over and the case is now closed.',
        channel='in_app'
    ))
    db.session.commit()

    flash(f'Handover recorded. Item marked as closed.', 'success')
    return redirect(url_for('admin.claims_list'))


# ── CREATE MATCH ──────────────────────────────────────────────────────────────
@bp.route('/matches/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_match():
    if request.method == 'POST':
        lost_item_id  = request.form.get('lost_item_id',  type=int)
        found_item_id = request.form.get('found_item_id', type=int)

        if not lost_item_id or not found_item_id:
            flash('Both a lost item and a found item must be selected.', 'danger')
            return redirect(url_for('admin.create_match'))

        lost_item  = Item.query.get_or_404(lost_item_id)
        found_item = Item.query.get_or_404(found_item_id)

        if lost_item.type != 'lost' or found_item.type != 'found':
            flash('Invalid selection. First item must be lost, second must be found.', 'danger')
            return redirect(url_for('admin.create_match'))

        # Check match doesn't already exist
        existing = Match.query.filter_by(
            lost_item_id=lost_item_id,
            found_item_id=found_item_id
        ).first()
        if existing:
            flash('A match between these two items already exists.', 'warning')
            return redirect(url_for('admin.create_match'))

        match = Match(
            lost_item_id=lost_item_id,
            found_item_id=found_item_id,
            matched_by=current_user.id,
            match_method='manual'
        )
        db.session.add(match)

        lost_item.status  = 'matched'
        found_item.status = 'matched'

        # Notify both parties
        db.session.add(Notification(
            user_id=lost_item.reported_by,
            related_item_id=found_item.id,
            type='match_found',
            message=f'A potential match has been found for your lost item '
                    f'"{lost_item.title}" ({lost_item.reference_number}). '
                    f'Log in to view the found item and submit a claim.',
            channel='in_app'
        ))
        db.session.add(Notification(
            user_id=found_item.reported_by,
            related_item_id=found_item.id,
            type='match_found',
            message=f'The item you found ("{found_item.title}", '
                    f'{found_item.reference_number}) has been matched to '
                    f'a lost item report. The owner has been notified.',
            channel='in_app'
        ))
        db.session.commit()

        flash('Match created successfully. Both parties have been notified.', 'success')
        return redirect(url_for('admin.dashboard'))

    lost_items  = Item.query.filter_by(type='lost',  status='open').all()
    found_items = Item.query.filter_by(type='found', status='open').all()
    return render_template('admin/create_match.html',
                           lost_items=lost_items,
                           found_items=found_items)


# ── MANAGE ITEMS ──────────────────────────────────────────────────────────────
@bp.route('/items')
@login_required
@admin_required
def manage_items():
    status_filter = request.args.get('status', 'all')
    valid = ['all', 'open', 'matched', 'claimed', 'closed']

    if status_filter not in valid:
        status_filter = 'all'

    query = Item.query
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)

    items = query.order_by(Item.created_at.desc()).all()
    return render_template('admin/manage_items.html',
                           items=items,
                           status_filter=status_filter)


# ── MANAGE USERS ──────────────────────────────────────────────────────────────
@bp.route('/users')
@login_required
@admin_required
def manage_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/manage_users.html', users=users)


@bp.route('/users/<int:user_id>/toggle-role', methods=['POST'])
@login_required
@admin_required
def toggle_role(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash('You cannot change your own role.', 'danger')
        return redirect(url_for('admin.manage_users'))

    user.role = 'admin' if user.role == 'student' else 'student'
    db.session.commit()
    flash(f'{user.name} is now a {user.role}.', 'success')
    return redirect(url_for('admin.manage_users'))