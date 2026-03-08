from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app.items import bp
from app import db
from app.models.item import Item
from app.models.notification import Notification
from werkzeug.utils import secure_filename
import os
import secrets
from datetime import datetime

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file):
    """Saves file to static/uploads and returns the relative path, or None."""
    if not file or file.filename == '':
        return None
    if not allowed_file(file.filename):
        return None
    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f"{secrets.token_hex(12)}.{ext}"
    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    file.save(os.path.join(upload_folder, unique_name))
    return f"uploads/{unique_name}"


# ── HOME ──────────────────────────────────────────────────────────────────────
@bp.route('/')
def index():
    recent_lost = Item.query.filter_by(type='lost', status='open')\
                             .order_by(Item.created_at.desc()).limit(6).all()
    recent_found = Item.query.filter_by(type='found', status='open')\
                              .order_by(Item.created_at.desc()).limit(6).all()
    return render_template('items/index.html',
                           recent_lost=recent_lost,
                           recent_found=recent_found)


# ── REPORT ITEM ───────────────────────────────────────────────────────────────
@bp.route('/report', methods=['GET', 'POST'])
@login_required
def report():
    categories = ['Electronics', 'Clothing', 'Documents', 'Keys', 'Bags', 'Stationery', 'Accessories', 'Other']
    campuses = ['Steve Biko', 'Ritson', 'ML Sultan']

    if request.method == 'POST':
        item_type = request.form.get('type', '').strip()
        title = request.form.get('title', '').strip()
        category = request.form.get('category', '').strip()
        campus = request.form.get('campus', '').strip()
        location = request.form.get('location', '').strip()
        date_str = request.form.get('date_of_incident', '').strip()
        public_description = request.form.get('public_description', '').strip()
        private_verification = request.form.get('private_verification', '').strip()
        photo = request.files.get('photo')

        # ── Validation ────────────────────────────────────────────────────
        errors = []

        if item_type not in ['lost', 'found']:
            errors.append('Please select Lost or Found.')
        if not title:
            errors.append('Item title is required.')
        if category not in categories:
            errors.append('Please select a valid category.')
        if campus not in campuses:
            errors.append('Please select a valid campus.')
        if not public_description:
            errors.append('Public description is required.')
        if not private_verification:
            errors.append('Private verification details are required.')

        date_of_incident = None
        if date_str:
            try:
                date_of_incident = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                errors.append('Invalid date format.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('items/report.html',
                                   categories=categories,
                                   campuses=campuses,
                                   form_data=request.form)

        # ── Save Photo ────────────────────────────────────────────────────
        image_path = save_uploaded_file(photo)

        # ── Generate Reference Number ─────────────────────────────────────
        reference_number = Item.generate_reference_number()

        # ── Save Item ─────────────────────────────────────────────────────
        item = Item(
            reported_by=current_user.id,
            reference_number=reference_number,
            type=item_type,
            title=title,
            category=category,
            campus=campus,
            location=location if location else None,
            date_of_incident=date_of_incident,
            public_description=public_description,
            private_verification=private_verification,
            image_path=image_path,
            status='open'
        )
        db.session.add(item)
        db.session.flush()

        # ── Notify Admin ──────────────────────────────────────────────────
        from app.models.user import User
        admins = User.query.filter_by(role='admin').all()
        for admin in admins:
            notif = Notification(
                user_id=admin.id,
                related_item_id=item.id,
                type='claim_submitted',
                message=f'New {item_type} item reported: "{title}" ({reference_number}) at {campus}.',
                channel='in_app'
            )
            db.session.add(notif)

        db.session.commit()

        flash(f'Item reported successfully. Your reference number is <strong>{reference_number}</strong>.', 'success')
        return redirect(url_for('items.detail', item_id=item.id))

    return render_template('items/report.html',
                           categories=categories,
                           campuses=campuses,
                           form_data={})


# ── SEARCH ────────────────────────────────────────────────────────────────────
@bp.route('/search')
def search():
    item_type = request.args.get('type', '')
    category = request.args.get('category', '')
    campus = request.args.get('campus', '')
    keyword = request.args.get('keyword', '').strip()

    categories = ['Electronics', 'Clothing', 'Documents', 'Keys', 'Bags', 'Stationery', 'Accessories', 'Other']
    campuses = ['Steve Biko', 'Ritson', 'ML Sultan']

    query = Item.query.filter(Item.status.in_(['open', 'matched']))

    if item_type in ['lost', 'found']:
        query = query.filter_by(type=item_type)
    if category in categories:
        query = query.filter_by(category=category)
    if campus in campuses:
        query = query.filter_by(campus=campus)
    if keyword:
        query = query.filter(
            db.or_(
                Item.title.ilike(f'%{keyword}%'),
                Item.public_description.ilike(f'%{keyword}%')
            )
        )

    items = query.order_by(Item.created_at.desc()).all()

    return render_template('items/search.html',
                           items=items,
                           categories=categories,
                           campuses=campuses,
                           filters={
                               'type': item_type,
                               'category': category,
                               'campus': campus,
                               'keyword': keyword
                           })


# ── ITEM DETAIL ───────────────────────────────────────────────────────────────
@bp.route('/<int:item_id>')
def detail(item_id):
    item = Item.query.get_or_404(item_id)

    can_claim = (
        current_user.is_authenticated
        and not current_user.is_admin
        and item.type == 'found'
        and item.status in ['open', 'matched']
        and item.reported_by != current_user.id
    )

    return render_template('items/detail.html',
                           item=item,
                           can_claim=can_claim)