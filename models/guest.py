from datetime import datetime
from flask import g
from models import db

class Guest(db.Model):
    __tablename__ = 'event_qr_codes'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    guest_name = db.Column(db.String(200), nullable=False)
    rollno = db.Column(db.String(20), nullable=False)
    mobile = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    qr_code = db.Column(db.String(255), unique=True, nullable=False, index=True)
    qr_image = db.Column(db.String(255), nullable=True)
    invite_sent = db.Column(db.Boolean, default=False, nullable=False)
    status = db.Column(db.String(50), default='ACTIVE', nullable=False)
    is_scanned = db.Column(db.Boolean, default=False, nullable=False)
    scanned_at = db.Column(db.DateTime, nullable=True)
    device_ip = db.Column(db.String(100), nullable=True)
    device_id = db.Column(db.String(255), nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_scanned_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<Guest {self.guest_name} ({self.email})>"

    @property
    def email_status(self):
        if self.invite_sent:
            return 'Sent'
        elif self.remarks:
            return 'Failed'
        else:
            return 'Pending'

    @property
    def whatsapp_sent(self):
        statuses = self._get_whatsapp_statuses()
        return statuses.get(str(self.id), {}).get('sent', False)

    @property
    def whatsapp_remarks(self):
        statuses = self._get_whatsapp_statuses()
        return statuses.get(str(self.id), {}).get('remarks', None)

    @property
    def whatsapp_status(self):
        if self.whatsapp_sent:
            return 'Sent'
        elif self.whatsapp_remarks:
            return 'Failed'
        else:
            return 'Pending'

    def _get_whatsapp_statuses(self):
        if not hasattr(g, 'whatsapp_statuses'):
            import json
            import os
            from flask import current_app
            try:
                status_file = os.path.join(current_app.instance_path, 'whatsapp_status.json')
                if os.path.exists(status_file):
                    with open(status_file, 'r') as f:
                        g.whatsapp_statuses = json.load(f)
                else:
                    g.whatsapp_statuses = {}
            except Exception:
                g.whatsapp_statuses = {}
        return g.whatsapp_statuses


