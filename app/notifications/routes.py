from flask import render_template, jsonify, redirect, url_for, request
from flask_login import login_required, current_user
from app.notifications import bp
from app import db
from app.models.notification import Notification


# ── NOTIFICATION PAGE ─────────────────────────────────────────────────────────
@bp.route('/')
@login_required
def index():
    notifications = Notification.query\
        .filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc())\
        .all()

    # Mark all as read when the page is opened
    Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).update({'is_read': True})
    db.session.commit()

    return render_template('notifications/index.html',
                           notifications=notifications)


# ── AJAX COUNT — polled by base.html every 30 seconds ─────────────────────────
@bp.route('/api/count')
@login_required
def api_count():
    count = Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).count()
    return jsonify({'unread': count})


# ── MARK SINGLE READ ──────────────────────────────────────────────────────────
@bp.route('/mark-read/<int:notif_id>')
@login_required
def mark_read(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    if notif.user_id == current_user.id:
        notif.is_read = True
        db.session.commit()
    return redirect(request.referrer or url_for('notifications.index'))


# ── MARK ALL READ ─────────────────────────────────────────────────────────────
@bp.route('/mark-all-read')
@login_required
def mark_all_read():
    Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).update({'is_read': True})
    db.session.commit()
    return redirect(url_for('notifications.index'))