from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.matching import bp
from app import db
from app.models.item import Item
from app.models.match import Match
from app.models.notification import Notification
from app.matching.engine import MatchingEngine
from datetime import datetime

engine = MatchingEngine()

@bp.route('/item/<int:item_id>/matches')
@login_required
def view_matches(item_id):
    """View potential matches for an item"""
    item = Item.query.get_or_404(item_id)
    
    # Only admin or item owner can view matches
    if not current_user.is_admin and current_user.id != item.reported_by:
        flash('You do not have permission to view matches for this item.', 'danger')
        return redirect(url_for('items.detail', item_id=item_id))
    
    matches = engine.find_potential_matches(item)
    
    return render_template('matching/matches.html', 
                         item=item, 
                         matches=matches)

@bp.route('/admin/matches/<int:item_id>')
@login_required
def admin_view_matches(item_id):
    """Admin view to see potential matches for an item"""
    if not current_user.is_admin:
        flash('Admin access required.', 'danger')
        return redirect(url_for('items.index'))
    
    item = Item.query.get_or_404(item_id)
    matches = engine.find_potential_matches(item)
    
    return render_template('admin/matches/view.html', 
                         item=item, 
                         matches=matches)

@bp.route('/admin/confirm-match', methods=['POST'])
@login_required
def confirm_match():
    """Admin confirms a match between lost and found items"""
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    lost_id = request.form.get('lost_id')
    found_id = request.form.get('found_id')
    
    if not lost_id or not found_id:
        flash('Missing item IDs.', 'danger')
        return redirect(url_for('admin.dashboard'))
    
    lost_item = Item.query.get(lost_id)
    found_item = Item.query.get(found_id)
    
    if not lost_item or not found_item:
        flash('Items not found.', 'danger')
        return redirect(url_for('admin.dashboard'))
    
    # Create match record
    match = Match(
        lost_item_id=lost_id,
        found_item_id=found_id,
        matched_by=current_user.id,
        match_method='manual',
        created_at=datetime.utcnow()
    )
    
    # Update both items status
    lost_item.status = 'matched'
    found_item.status = 'matched'
    
    db.session.add(match)
    
    # Notify both users
    notif_lost = Notification(
        user_id=lost_item.reported_by,
        related_item_id=lost_id,
        type='match_found',
        message=f'An admin has confirmed a match for your lost item: {found_item.title}. Please check your dashboard.',
        channel='in_app'
    )
    
    notif_found = Notification(
        user_id=found_item.reported_by,
        related_item_id=found_id,
        type='match_found',
        message=f'An admin has confirmed that your found item matches a lost item: {lost_item.title}. Please check your dashboard.',
        channel='in_app'
    )
    
    db.session.add_all([notif_lost, notif_found])
    db.session.commit()
    
    flash(f'Match confirmed between {lost_item.reference_number} and {found_item.reference_number}. Users notified.', 'success')
    return redirect(url_for('admin.claims_list'))

@bp.route('/admin/reject-match', methods=['POST'])
@login_required
def reject_match():
    """Admin rejects a potential match"""
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    lost_id = request.form.get('lost_id')
    found_id = request.form.get('found_id')
    
    # Just create a notification that match was rejected
    # Items remain open for other matches
    
    flash('Match rejected.', 'info')
    return redirect(url_for('admin.dashboard'))

@bp.route('/admin/auto-match')
@login_required
def run_auto_match():
    """Manually trigger auto-matching job"""
    if not current_user.is_admin:
        flash('Admin access required.', 'danger')
        return redirect(url_for('items.index'))
    
    count = engine.auto_match_job()
    
    flash(f'Auto-matching complete. Created {count} notifications.', 'success')
    return redirect(url_for('admin.dashboard'))

@bp.route('/api/matches/<int:item_id>')
@login_required
def api_matches(item_id):
    """API endpoint to get matches for an item"""
    item = Item.query.get_or_404(item_id)
    
    # Check permission
    if not current_user.is_admin and current_user.id != item.reported_by:
        return jsonify({'error': 'Unauthorized'}), 403
    
    matches = engine.find_potential_matches(item)
    
    # Format for JSON response
    result = []
    for match in matches:
        result.append({
            'id': match['item'].id,
            'reference': match['item'].reference_number,
            'title': match['item'].title,
            'type': match['type'],
            'score': match['score'],
            'breakdown': match['breakdown']
        })
    
    return jsonify(result)
