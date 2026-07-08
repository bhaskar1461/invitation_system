from flask import Blueprint, render_template
from flask_login import login_required
from datetime import datetime, timedelta

from models import db
from models.guest import Guest
from models.email_log import EmailLog
from forms import EmptyForm

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@login_required
def index():
    # Calculate stats
    total_guests = Guest.query.count()
    sent_count = Guest.query.filter_by(email_status='Sent').count()
    pending_count = Guest.query.filter_by(email_status='Pending').count()
    failed_count = Guest.query.filter_by(email_status='Failed').count()

    # Time-based stats
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    week_start = today_start - timedelta(days=7) # Last 7 days
    
    added_today = Guest.query.filter(Guest.created_at >= today_start).count()
    added_this_week = Guest.query.filter(Guest.created_at >= week_start).count()

    # Recent guest entries (last 5)
    recent_guests = Guest.query.order_by(Guest.created_at.desc()).limit(5).all()

    action_form = EmptyForm()

    return render_template(
        'dashboard.html',
        total_guests=total_guests,
        sent_count=sent_count,
        pending_count=pending_count,
        failed_count=failed_count,
        added_today=added_today,
        added_this_week=added_this_week,
        recent_guests=recent_guests,
        action_form=action_form
    )

@dashboard_bp.route('/reports')
@login_required
def reports():
    # Fetch general statistics
    total_guests = Guest.query.count()
    sent_count = Guest.query.filter_by(email_status='Sent').count()
    pending_count = Guest.query.filter_by(email_status='Pending').count()
    failed_count = Guest.query.filter_by(email_status='Failed').count()

    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    week_start = today_start - timedelta(days=7)

    added_today = Guest.query.filter(Guest.created_at >= today_start).count()
    added_this_week = Guest.query.filter(Guest.created_at >= week_start).count()

    # Fetch last 15 failed email logs with guest details
    failed_logs = db.session.query(EmailLog, Guest).join(Guest).filter(EmailLog.status == 'Failed').order_by(EmailLog.sent_at.desc()).limit(15).all()
    
    # Calculate percentages
    delivery_rate = 0.0
    if total_guests > 0:
        delivery_rate = round((sent_count / total_guests) * 100, 1)

    return render_template(
        'guests/reports.html',
        total_guests=total_guests,
        sent_count=sent_count,
        pending_count=pending_count,
        failed_count=failed_count,
        added_today=added_today,
        added_this_week=added_this_week,
        failed_logs=failed_logs,
        delivery_rate=delivery_rate
    )
