from datetime import datetime
from app import db

class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    related_item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=True)

    type = db.Column(
        db.Enum(
            'match_found', 'claim_submitted', 'claim_approved',
            'claim_rejected', 'expiry_warning', 'item_closed',
            name='notification_type_enum'
        ),
        nullable=False
    )
    message = db.Column(db.Text, nullable=False)
    channel = db.Column(
        db.Enum('email', 'in_app', name='channel_enum'),
        nullable=False,
        default='in_app'
    )
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<Notification {self.type} → user={self.user_id} | read={self.is_read}>'
