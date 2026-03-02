from datetime import datetime
from app import db

class Item(db.Model):
    __tablename__ = 'items'

    id = db.Column(db.Integer, primary_key=True)
    reported_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reference_number = db.Column(db.String(20), nullable=False, unique=True, index=True)

    type = db.Column(db.Enum('lost', 'found', name='item_type_enum'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    category = db.Column(
        db.Enum('Electronics', 'Clothing', 'Documents',
                'Keys', 'Bags', 'Stationery', 'Accessories', 'Other',
                name='category_enum'),
        nullable=False
    )

    public_description = db.Column(db.Text, nullable=False)
    private_verification = db.Column(db.Text, nullable=True)

    location = db.Column(db.String(200), nullable=True)
    campus = db.Column(
        db.Enum('Steve Biko', 'Ritson', 'ML Sultan', name='item_campus_enum'),
        nullable=True
    )
    image_path = db.Column(db.String(255), nullable=True)
    date_of_incident = db.Column(db.Date, nullable=True)

    status = db.Column(
        db.Enum('open', 'matched', 'claimed', 'closed', name='item_status_enum'),
        nullable=False,
        default='open'
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<Item {self.reference_number} | {self.type} | {self.status}>'
    
    @staticmethod
    def generate_reference_number():
        """Generate a unique reference number like LF-2026-00142."""
        last = Item.query.order_by(Item.id.desc()).first()
        next_id = (last.id + 1) if last else 1
        year = datetime.utcnow().year
        return f'LF-{year}-{next_id:05d}'
