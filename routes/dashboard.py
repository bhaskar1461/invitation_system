from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required
from datetime import datetime, timedelta

from models import db
from models.guest import Guest
from forms import EmptyForm

dashboard_bp = Blueprint('dashboard', __name__)

def _get_whatsapp_stats(total_guests):
    import json
    import os
    from flask import current_app
    status_file = os.path.join(current_app.instance_path, 'whatsapp_status.json')
    whatsapp_data = {}
    if os.path.exists(status_file):
        try:
            with open(status_file, 'r') as f:
                whatsapp_data = json.load(f)
        except Exception:
            pass
            
    sent_ids = [int(gid) for gid, val in whatsapp_data.items() if val.get('sent', False)]
    failed_ids = [int(gid) for gid, val in whatsapp_data.items() if not val.get('sent', False) and val.get('remarks') is not None]
    
    whatsapp_sent_count = Guest.query.filter(Guest.id.in_(sent_ids)).count() if sent_ids else 0
    whatsapp_failed_count = Guest.query.filter(Guest.id.in_(failed_ids)).count() if failed_ids else 0
    whatsapp_pending_count = total_guests - whatsapp_sent_count - whatsapp_failed_count
    
    return whatsapp_sent_count, whatsapp_pending_count, whatsapp_failed_count, failed_ids

@dashboard_bp.route('/dashboard')
@login_required
def index():
    # Calculate stats
    total_guests = Guest.query.count()
    sent_count = Guest.query.filter_by(invite_sent=True).count()
    pending_count = Guest.query.filter(Guest.invite_sent == False, Guest.remarks == None).count()
    failed_count = Guest.query.filter(Guest.invite_sent == False, Guest.remarks != None).count()
    
    whatsapp_sent_count, whatsapp_pending_count, whatsapp_failed_count, _ = _get_whatsapp_stats(total_guests)
    
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
        whatsapp_sent_count=whatsapp_sent_count,
        whatsapp_pending_count=whatsapp_pending_count,
        whatsapp_failed_count=whatsapp_failed_count,
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

    whatsapp_sent_count, whatsapp_pending_count, whatsapp_failed_count, failed_ids = _get_whatsapp_stats(total_guests)

    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    week_start = today_start - timedelta(days=7)

    added_today = Guest.query.filter(Guest.created_at >= today_start).count()
    added_this_week = Guest.query.filter(Guest.created_at >= week_start).count()

    # Fetch last 15 failed email and whatsapp logs
    failed_logs = Guest.query.filter(Guest.invite_sent == False, Guest.remarks != None).order_by(Guest.updated_at.desc()).limit(15).all()
    whatsapp_failed_logs = Guest.query.filter(Guest.id.in_(failed_ids)).order_by(Guest.updated_at.desc()).limit(15).all() if failed_ids else []
    
    # Calculate percentages
    delivery_rate = 0.0
    if total_guests > 0:
        delivery_rate = round((sent_count / total_guests) * 100, 1)

    whatsapp_delivery_rate = 0.0
    if total_guests > 0:
        whatsapp_delivery_rate = round((whatsapp_sent_count / total_guests) * 100, 1)

    return render_template(
        'guests/reports.html',
        total_guests=total_guests,
        sent_count=sent_count,
        pending_count=pending_count,
        failed_count=failed_count,
        whatsapp_sent_count=whatsapp_sent_count,
        whatsapp_pending_count=whatsapp_pending_count,
        whatsapp_failed_count=whatsapp_failed_count,
        added_today=added_today,
        added_this_week=added_this_week,
        failed_logs=failed_logs,
        whatsapp_failed_logs=whatsapp_failed_logs,
        delivery_rate=delivery_rate,
        whatsapp_delivery_rate=whatsapp_delivery_rate
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

@dashboard_bp.route('/ticket/<string:qr_code>')
def view_ticket(qr_code):
    guest = Guest.query.filter_by(qr_code=qr_code).first_or_404()
    
    # Generate the barcode overlay image dynamically if it is missing
    import os
    barcode_full_path = os.path.join(current_app.root_path, f"static/barcodes/{guest.qr_code}.png")
    if not os.path.exists(barcode_full_path):
        try:
            from services.barcode_service import BarcodeService
            BarcodeService.generate_barcode(guest.qr_code)
        except Exception as e:
            current_app.logger.error(f"Error generating barcode overlay on ticket view: {str(e)}")
            
    return render_template('guests/view_ticket.html', guest=guest)

