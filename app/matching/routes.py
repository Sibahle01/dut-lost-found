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
    item = Item.query.get_or_404(item_id)
    if not current_user.is_admin and current_user.id != item.reported_by:
        flash('Access denied.', 'danger')
        return redirect(url_for('items.detail', item_id=item_id))
    
    from app.matching.engine import MatchingEngine
    engine = MatchingEngine()
    potential_matches = engine.find_potential_matches(item, min_score=50)
    
    # Enhance matches with lost_item and found_item for the form
    enhanced_matches = []
    for match in potential_matches:
        if item.type == 'lost':
            lost_item = item
            found_item = match['item']
        else:
            lost_item = match['item']
            found_item = item
        
        enhanced_matches.append({
            'item': match['item'],
            'score': match['score'],
            'breakdown': match['breakdown'],
            'lost_item': lost_item,
            'found_item': found_item
        })
    
    return render_template('admin/matches/view.html',
                           item=item, matches=enhanced_matches)
    from app.models.match import Match
    from app.matching.engine import MatchingEngine
    
    engine = MatchingEngine()
    
    if item.type == 'lost':
        matches = Match.query.filter_by(lost_item_id=item_id).all()
    else:
        matches = Match.query.filter_by(found_item_id=item_id).all()
    
    # Calculate scores for each match
    enhanced_matches = []
    for match in matches:
        if item.type == 'lost':
            lost_item = item
            found_item = match.found_item
        else:
            lost_item = match.lost_item
            found_item = item
        
        # Calculate match score - handle both dict and int returns
        result = engine.calculate_match_score(lost_item, found_item)
        
        # Check if result is a dictionary or just a number
        if isinstance(result, dict):
            score = result.get('total', 0)
            breakdown = result.get('breakdown', {})
        else:
            score = result
            breakdown = {
                'category': 0, 'campus': 0, 'title': 0,
                'description': 0, 'date': 0, 'location': 0
            }
        
        enhanced_matches.append({
            'item': found_item if item.type == 'lost' else lost_item,
            'score': score,
            'breakdown': breakdown,
            'type': 'found' if item.type == 'lost' else 'lost',
            'match_id': match.id,
            'lost_item': lost_item,
            'found_item': found_item
        })
    
    return render_template('admin/matches/view.html',
                           item=item, matches=enhanced_matches)

@bp.route('/admin/matches/<int:item_id>')
@login_required
def admin_view_matches(item_id):
    """Admin view to see potential matches for a specific item"""
    if not current_user.is_admin:
        flash('Admin access required.', 'danger')
        return redirect(url_for('items.index'))
    
    item = Item.query.get_or_404(item_id)
    
    # Only show matches for this specific item
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
        flash(f'Missing item IDs. Lost: {lost_id}, Found: {found_id}', 'danger')
        return redirect(url_for('admin.dashboard'))
    
    lost_item = Item.query.get(lost_id)
    found_item = Item.query.get(found_id)
    
    if not lost_item or not found_item:
        flash('Items not found.', 'danger')
        return redirect(url_for('admin.dashboard'))
    
    # Check if match already exists
    existing_match = Match.query.filter_by(
        lost_item_id=lost_id,
        found_item_id=found_id
    ).first()
    
    if existing_match:
        flash('This match already exists.', 'warning')
        return redirect(url_for('admin.dashboard'))
    
    # Create match record
    match = Match(
        lost_item_id=lost_id,
        found_item_id=found_id,
        matched_by=current_user.id,
        match_method='manual'
    )
    db.session.add(match)
    
    # Update both items status
    lost_item.status = 'matched'
    found_item.status = 'matched'
    
    # Notify both users
    from app.models.notification import Notification
    notif_lost = Notification(
        user_id=lost_item.reported_by,
        related_item_id=lost_id,
        type='match_found',
        message=f'A match has been confirmed for your lost item "{lost_item.title}". Please visit the library at {lost_item.campus} campus to collect your item.',
        channel='in_app'
    )
    notif_found = Notification(
        user_id=found_item.reported_by,
        related_item_id=found_id,
        type='match_found',
        message=f'The item you found "{found_item.title}" has been matched with its owner. Thank you for your honesty!',
        channel='in_app'
    )
    db.session.add_all([notif_lost, notif_found])
    db.session.commit()
    
    flash(f'Match confirmed! Both parties have been notified.', 'success')
    return redirect(url_for('admin.claims_list'))
    
    lost_item = Item.query.get(lost_id)
    found_item = Item.query.get(found_id)
    
    if not lost_item or not found_item:
        flash('Items not found.', 'danger')
        return redirect(url_for('admin.dashboard'))
    
    # Check if match already exists
    existing_match = Match.query.filter_by(
        lost_item_id=lost_id,
        found_item_id=found_id
    ).first()
    
    if existing_match:
        flash('This match already exists.', 'warning')
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
    
    # ── NOTIFY THE PERSON WHO LOST THE ITEM ─────────────────────────────
    notif_lost = Notification(
        user_id=lost_item.reported_by,
        related_item_id=lost_id,
        type='match_found',
        message=f'✅ Good news! A potential match has been found for your lost item "{lost_item.title}". '
                f'Please visit the Library at {lost_item.campus} campus with your student card and proof of ownership '
                f'(receipt, photos, etc.) to collect your item. Our staff will assist you.',
        channel='in_app'
    )
    
    # ── NOTIFY THE PERSON WHO FOUND THE ITEM ────────────────────────────
    notif_found = Notification(
        user_id=found_item.reported_by,
        related_item_id=found_id,
        type='match_found',
        message=f'🙏 Thank you for your honesty! The item you found ("{found_item.title}") '
                f'has been matched with its owner. Please bring the item to the Library at {found_item.campus} campus '
                f'during operating hours. The owner has been notified and will collect it from there. '
                f'Thank you for helping someone recover their belonging!',
        channel='in_app'
    )
    
    # Add both notifications
    db.session.add(notif_lost)
    db.session.add(notif_found)
    db.session.commit()
    
    flash(f'✅ Match confirmed! Both parties have been notified.', 'success')
    return redirect(url_for('admin.claims_list'))

@bp.route('/admin/reject-match', methods=['POST'])
@login_required
def reject_match():
    """Admin rejects a potential match"""
    if not current_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    lost_id = request.form.get('lost_id')
    found_id = request.form.get('found_id')
    
    flash('Match rejected.', 'info')
    return redirect(url_for('admin.dashboard'))

@bp.route('/admin/auto-match')
@login_required
def run_auto_match():
    """Manually trigger auto-matching job"""
    if not current_user.is_admin:
        flash('Admin access required.', 'danger')
        return redirect(url_for('items.index'))
    
    try:
        count = engine.auto_match_job()
        if count == 0:
            flash('No potential matches found. Try creating more items with similar categories and campuses.', 'info')
        else:
            flash(f'Auto-matching complete. Found {count} potential match(es). Check your notifications.', 'success')
    except Exception as e:
        flash(f'Error during auto-match: {str(e)}', 'danger')
        print(f'Auto-match error: {e}')
    
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