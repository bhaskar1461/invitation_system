from datetime import datetime
from models import db

class EmailLog(db.Model):
    __tablename__ = 'email_logs'

    id = db.Column(db.Integer, primary_key=True)
    guest_id = db.Column(db.Integer, db.ForeignKey('event_qr_codes.id', ondelete='CASCADE'), nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    status = db.Column(db.String(20), nullable=False) # Sent, Failed
    error_message = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<EmailLog guest_id={self.guest_id} status={self.status}>"
