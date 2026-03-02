from datetime import datetime
from app import db

class Match(db.Model):
    __tablename__ = 'matches'

    id = db.Column(db.Integer, primary_key=True)
    lost_item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    found_item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    matched_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    match_method = db.Column(
        db.Enum('manual', 'system', name='match_method_enum'),
        nullable=False,
        default='manual'
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<Match lost={self.lost_item_id} <-> found={self.found_item_id}>'
