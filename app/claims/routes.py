from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app.claims import bp
from app import db
from app.models.claim import Claim
from app.models.item import Item
from app.models.notification import Notification
from app.models.user import User
from werkzeug.utils import secure_filename
import os
import secrets
from datetime import datetime

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_evidence_file(file):
    """Saves evidence file to static/uploads/evidence and returns path"""
    if not file or file.filename == '':
        return None
    if not allowed_file(file.filename):
        return None
    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f"evidence_{secrets.token_hex(8)}.{ext}"
    upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'evidence')
    os.makedirs(upload_folder, exist_ok=True)
    file.save(os.path.join(upload_folder, unique_name))
    return f"uploads/evidence/{unique_name}"


@bp.route('/submit/<int:item_id>', methods=['GET', 'POST'])
@login_required
def submit(item_id):
    """Submit a claim for a found item"""
    item = Item.query.get_or_404(item_id)
    
    # Only allow claiming found items
    if item.type != 'found':
        flash('You can only claim found items.', 'danger')
        return redirect(url_for('items.detail', item_id=item_id))
    
    # Can't claim your own item
    if item.reported_by == current_user.id:
        flash('You cannot claim an item you reported.', 'danger')
        return redirect(url_for('items.detail', item_id=item_id))
    
    # Check if already claimed
    existing_claim = Claim.query.filter_by(
        item_id=item_id, 
        claimant_id=current_user.id,
        status='pending'
    ).first()
    if existing_claim:
        flash('You already have a pending claim for this item.', 'warning')
        return redirect(url_for('claims.dashboard'))
    
    if request.method == 'POST':
        claim_description = request.form.get('claim_description', '').strip()
        verification_answers = request.form.get('verification_answers', '').strip()
        evidence = request.files.get('evidence')
        
        errors = []
        
        if not claim_description:
            errors.append('Please describe why this item belongs to you.')
        
        if not verification_answers:
            errors.append('Please answer the verification questions.')
        
        evidence_path = None
        if evidence and evidence.filename:
            evidence_path = save_evidence_file(evidence)
            if not evidence_path:
                errors.append('Invalid file type. Allowed: PNG, JPG, GIF, PDF')
        else:
            errors.append('Please upload evidence (receipt, photo, etc.)')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('claims/submit.html', item=item)
        
        # Create claim
        claim = Claim(
            item_id=item_id,
            claimant_id=current_user.id,
            claim_description=claim_description,
            verification_answers=verification_answers,
            evidence_path=evidence_path,
            status='pending'
        )
        
        db.session.add(claim)
        
        # Notify admins
        admins = User.query.filter_by(role='admin').all()
        for admin in admins:
            notif = Notification(
                user_id=admin.id,
                related_item_id=item_id,
                type='claim_submitted',
                message=f'New claim submitted for item: {item.title}',
                channel='in_app'
            )
            db.session.add(notif)
        
        db.session.commit()
        
        flash('Your claim has been submitted and is pending review.', 'success')
        return redirect(url_for('claims.dashboard'))
    
    return render_template('claims/submit.html', item=item)


@bp.route('/dashboard')
@login_required
def dashboard():
    """User dashboard showing their claims and reported items"""
    user_claims = Claim.query.filter_by(claimant_id=current_user.id)\
                             .order_by(Claim.created_at.desc())\
                             .all()
    
    user_items = Item.query.filter_by(reported_by=current_user.id)\
                           .order_by(Item.created_at.desc())\
                           .all()
    
    return render_template('claims/dashboard.html', 
                         claims=user_claims, 
                         items=user_items)


@bp.route('/my-claims')
@login_required
def my_claims():
    """List all claims by current user"""
    claims = Claim.query.filter_by(claimant_id=current_user.id)\
                        .order_by(Claim.created_at.desc())\
                        .all()
    return render_template('claims/my_claims.html', claims=claims)


@bp.route('/my-items')
@login_required
def my_items():
    """List all items reported by current user"""
    items = Item.query.filter_by(reported_by=current_user.id)\
                      .order_by(Item.created_at.desc())\
                      .all()
    return render_template('claims/my_items.html', items=items)
