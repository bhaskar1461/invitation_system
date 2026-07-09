from flask import Blueprint, redirect, url_for, flash, request, current_app
from flask_login import login_required

from models.guest import Guest
from forms import EmptyForm
from services.email_service import EmailService

email_bp = Blueprint('email', __name__, url_prefix='/email')

@email_bp.route('/<int:guest_id>/send', methods=['POST'])
@login_required
def send_single(guest_id):
    form = EmptyForm()
    if form.validate_on_submit():
        success, message = EmailService.send_invitation_email(guest_id)
        guest = Guest.query.get(guest_id)
        if success:
            flash(f"Invitation email dispatch initiated for {guest.guest_name}.", "success")
        else:
            flash(f"Failed to initiate email for {guest.guest_name}: {message}", "danger")
    else:
        flash("CSRF token verification failed.", "danger")
        
    return redirect(request.referrer or url_for('guests.index'))

@email_bp.route('/send_pending', methods=['POST'])
@login_required
def send_pending():
    form = EmptyForm()
    if form.validate_on_submit():
        pending_guests = Guest.query.filter(Guest.invite_sent == False, Guest.remarks.is_(None)).all()
        if not pending_guests:
            flash("No pending invitations to send.", "info")
            return redirect(request.referrer or url_for('guests.index'))
            
        guest_ids = [g.id for g in pending_guests]
        success, message = EmailService.send_bulk_invitations(guest_ids)
        if success:
            flash(f"Bulk dispatch initiated! Queued {len(guest_ids)} emails for sending.", "success")
        else:
            flash(f"Failed to initiate bulk dispatch: {message}", "danger")
    else:
        flash("CSRF token verification failed.", "danger")
        
    return redirect(request.referrer or url_for('guests.index'))

@email_bp.route('/retry_failed', methods=['POST'])
@login_required
def retry_failed():
    form = EmptyForm()
    if form.validate_on_submit():
        failed_guests = Guest.query.filter(Guest.invite_sent == False, Guest.remarks.is_not(None)).all()
        if not failed_guests:
            flash("No failed invitations to retry.", "info")
            return redirect(request.referrer or url_for('guests.index'))
            
        guest_ids = [g.id for g in failed_guests]
        success, message = EmailService.send_bulk_invitations(guest_ids)
        if success:
            flash(f"Retry dispatch initiated! Queued {len(guest_ids)} failed emails for retry.", "success")
        else:
            flash(f"Failed to initiate retry dispatch: {message}", "danger")
    else:
        flash("CSRF token verification failed.", "danger")
        
    return redirect(request.referrer or url_for('guests.index'))
