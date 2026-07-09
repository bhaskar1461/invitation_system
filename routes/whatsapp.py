from flask import Blueprint, redirect, url_for, flash, request, current_app
from flask_login import login_required

from models.guest import Guest
from forms import EmptyForm
from services.whatsapp_service import WhatsAppService

whatsapp_bp = Blueprint('whatsapp', __name__, url_prefix='/whatsapp')

@whatsapp_bp.route('/<int:guest_id>/send', methods=['POST'])
@login_required
def send_single(guest_id):
    form = EmptyForm()
    if form.validate_on_submit():
        success, message = WhatsAppService.send_invitation_whatsapp(guest_id)
        guest = Guest.query.get(guest_id)
        if success:
            flash(f"Invitation WhatsApp dispatch initiated for {guest.guest_name}.", "success")
        else:
            flash(f"Failed to initiate WhatsApp for {guest.guest_name}: {message}", "danger")
    else:
        flash("CSRF token verification failed.", "danger")
        
    return redirect(request.referrer or url_for('guests.index'))

@whatsapp_bp.route('/send_pending', methods=['POST'])
@login_required
def send_pending():
    form = EmptyForm()
    if form.validate_on_submit():
        all_guests = Guest.query.all()
        pending_guests = [g for g in all_guests if not g.whatsapp_sent and not g.whatsapp_remarks]
        if not pending_guests:
            flash("No pending WhatsApp invitations to send.", "info")
            return redirect(request.referrer or url_for('guests.index'))
            
        guest_ids = [g.id for g in pending_guests]
        success, message = WhatsAppService.send_bulk_invitations(guest_ids)
        if success:
            flash(f"Bulk WhatsApp dispatch initiated! Queued {len(guest_ids)} messages for sending.", "success")
        else:
            flash(f"Failed to initiate bulk WhatsApp dispatch: {message}", "danger")
    else:
        flash("CSRF token verification failed.", "danger")
        
    return redirect(request.referrer or url_for('guests.index'))

@whatsapp_bp.route('/retry_failed', methods=['POST'])
@login_required
def retry_failed():
    form = EmptyForm()
    if form.validate_on_submit():
        all_guests = Guest.query.all()
        failed_guests = [g for g in all_guests if not g.whatsapp_sent and g.whatsapp_remarks]
        if not failed_guests:
            flash("No failed WhatsApp invitations to retry.", "info")
            return redirect(request.referrer or url_for('guests.index'))
            
        guest_ids = [g.id for g in failed_guests]
        success, message = WhatsAppService.send_bulk_invitations(guest_ids)
        if success:
            flash(f"Retry WhatsApp dispatch initiated! Queued {len(guest_ids)} failed messages for retry.", "success")
        else:
            flash(f"Failed to initiate retry WhatsApp dispatch: {message}", "danger")
    else:
        flash("CSRF token verification failed.", "danger")
        
    return redirect(request.referrer or url_for('guests.index'))
