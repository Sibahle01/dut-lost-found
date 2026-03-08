from datetime import datetime
from app import db


class Claim(db.Model):
    __tablename__ = 'claims'

    id                     = db.Column(db.Integer, primary_key=True)
    item_id                = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    claimant_id            = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reviewed_by            = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    claim_description      = db.Column(db.Text, nullable=False)
    verification_answers   = db.Column(db.Text, nullable=True)
    evidence_path          = db.Column(db.String(255), nullable=False)
    status                 = db.Column(
        db.Enum('pending', 'approved', 'rejected', name='claim_status_enum'),
        nullable=False,
        default='pending'
    )
    rejection_reason       = db.Column(db.Text, nullable=True)
    created_at             = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at            = db.Column(db.DateTime, nullable=True)
    handover_logged_at     = db.Column(db.DateTime, nullable=True)
    handover_student_number = db.Column(db.String(20), nullable=True)

    # Note: 'item', 'claimant', 'reviewer' backref names come from
    # the relationships defined in Item and User models respectively.

    def __repr__(self):
        return f'<Claim {self.id} | item={self.item_id} | {self.status}>'