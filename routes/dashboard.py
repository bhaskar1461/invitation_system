from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from datetime import datetime, timedelta

from models import db
from models.guest import Guest
from forms import EmptyForm

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@login_required
def index():
    # Calculate stats
    total_guests = Guest.query.count()
    sent_count = Guest.query.filter_by(invite_sent=True).count()
    pending_count = Guest.query.filter(Guest.invite_sent == False, Guest.remarks == None).count()
    failed_count = Guest.query.filter(Guest.invite_sent == False, Guest.remarks != None).count()
    scanned_count = Guest.query.filter_by(is_scanned=True).count()

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
        scanned_count=scanned_count,
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
    sent_count = Guest.query.filter_by(invite_sent=True).count()
    pending_count = Guest.query.filter(Guest.invite_sent == False, Guest.remarks == None).count()
    failed_count = Guest.query.filter(Guest.invite_sent == False, Guest.remarks != None).count()

    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    week_start = today_start - timedelta(days=7)

    added_today = Guest.query.filter(Guest.created_at >= today_start).count()
    added_this_week = Guest.query.filter(Guest.created_at >= week_start).count()

    # Fetch last 15 failed email logs
    failed_logs = Guest.query.filter(Guest.invite_sent == False, Guest.remarks != None).order_by(Guest.updated_at.desc()).limit(15).all()
    
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

@dashboard_bp.route('/scan/<string:qr_code>')
@login_required
def scan_verify(qr_code):
    # Query with row-level transaction locking to prevent gate concurrency check-in race conditions
    guest = db.session.query(Guest).filter_by(qr_code=qr_code).with_for_update().first()
    if not guest:
        return render_template('guests/scan_result.html', status='invalid', qr_code=qr_code), 404
        
    if guest.is_scanned:
        return render_template('guests/scan_result.html', status='already_scanned', guest=guest)
    
    # Mark as scanned
    guest.is_scanned = True
    guest.scanned_at = datetime.utcnow()
    guest.last_scanned_at = datetime.utcnow()
    guest.device_ip = request.remote_addr
    guest.device_id = request.headers.get('User-Agent', '')[:100]
    db.session.commit()
    
    return render_template('guests/scan_result.html', status='success', guest=guest)

