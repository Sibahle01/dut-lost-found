from flask_login import UserMixin
from datetime import datetime
from app import db
import bcrypt


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id                 = db.Column(db.Integer, primary_key=True)
    name               = db.Column(db.String(100), nullable=False)
    student_number     = db.Column(db.String(20), nullable=True)
    email              = db.Column(db.String(150), nullable=False, unique=True, index=True)
    password_hash      = db.Column(db.String(255), nullable=False)
    role               = db.Column(db.String(10), nullable=False, default='student')
    campus             = db.Column(
        db.Enum('Steve Biko', 'Ritson', 'ML Sultan', name='campus_enum'),
        nullable=True
    )
    is_verified        = db.Column(db.Boolean, default=False, nullable=False)
    verification_token = db.Column(db.String(100), nullable=True, unique=True)
    created_at         = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # ── Relationships ─────────────────────────────────────────────────────────
    reported_items = db.relationship(
        'Item',
        foreign_keys='Item.reported_by',
        backref='reporter',
        lazy='dynamic'
    )
    submitted_claims = db.relationship(
        'Claim',
        foreign_keys='Claim.claimant_id',
        backref='claimant',
        lazy='dynamic'
    )
    reviewed_claims = db.relationship(
        'Claim',
        foreign_keys='Claim.reviewed_by',
        backref='reviewer',
        lazy='dynamic'
    )
    notifications = db.relationship(
        'Notification',
        foreign_keys='Notification.user_id',
        backref='recipient',
        lazy='dynamic'
    )

    # ── Methods ───────────────────────────────────────────────────────────────
    def set_password(self, plain_password):
        self.password_hash = bcrypt.hashpw(
            plain_password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

    def check_password(self, plain_password):
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            self.password_hash.encode('utf-8')
        )

    @staticmethod
    def is_dut_email(email):
        email = email.strip().lower()
        return email.endswith('@dut.ac.za') or email.endswith('@dut4life.ac.za')

    @property
    def is_admin(self):
        return self.role == 'admin'

    def __repr__(self):
        return f'<User {self.email} | {self.role}>'