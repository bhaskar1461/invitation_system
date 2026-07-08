from datetime import datetime
from models import db

class Guest(db.Model):
    __tablename__ = 'event_qr_codes'

    # Existing table columns
    id = db.Column(db.Integer, primary_key=True)
    guest_name = db.Column(db.String(100), nullable=False)
    rollno = db.Column(db.String(50), nullable=True)
    mobile = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    qr_code = db.Column(db.String(50), unique=True, nullable=False)
    qr_image = db.Column(db.String(255), nullable=True)
    invite_sent = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(50), default='Pending')
    is_scanned = db.Column(db.Boolean, default=False)
    scanned_at = db.Column(db.DateTime, nullable=True)
    device_ip = db.Column(db.String(50), nullable=True)
    device_id = db.Column(db.String(100), nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_scanned_at = db.Column(db.DateTime, nullable=True)

    # Required enhancements
    created_by = db.Column(db.Integer, nullable=True)
    updated_by = db.Column(db.Integer, nullable=True)
    email_status = db.Column(db.String(50), default='Pending')
    email_sent_at = db.Column(db.DateTime, nullable=True)
    email_retry_count = db.Column(db.Integer, default=0)
    last_email_error = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<Guest {self.guest_name} ({self.email})>"

# Automatic ORM query visibility filter for developer-created guests using created_by column
from flask import has_request_context
from flask_login import current_user
from sqlalchemy import event
from sqlalchemy.orm import Query

@event.listens_for(Query, "before_compile", retval=True)
def filter_developer_guests(query):
    """
    Automatically intercepts and filters out developer-created guests
    if the logged-in user is an Admin (non-developer).
    """
    if has_request_context() and current_user and current_user.is_authenticated:
        if not getattr(current_user, 'is_developer', False):
            # Scan query descriptors to check if it targets the Guest entity
            targets_guest = False
            for desc in query.column_descriptions:
                entity = desc.get('entity')
                if entity and issubclass(entity, Guest):
                    targets_guest = True
                    break
            
            if targets_guest:
                # Save limit/offset clauses if they exist to avoid InvalidRequestError
                limit_clause = getattr(query, '_limit_clause', None)
                offset_clause = getattr(query, '_offset_clause', None)
                query._limit_clause = None
                query._offset_clause = None
                
                query = query.filter((Guest.created_by != 2) | (Guest.created_by == None))
                
                # Re-apply limit and offset clauses
                query._limit_clause = limit_clause
                query._offset_clause = offset_clause
    return query
