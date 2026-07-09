from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required

from models import db
from models.guest import Guest
from forms import GuestForm, EmptyForm
from services.guest_service import GuestService

guests_bp = Blueprint('guests', __name__, url_prefix='/guests')

@guests_bp.route('/', methods=['GET'])
@login_required
def index():
    # Parse query parameters
    search = request.args.get('search', '').strip()
    status = request.args.get('status', '').strip()
    sort_by = request.args.get('sort_by', 'created_at').strip()
    sort_dir = request.args.get('sort_dir', 'desc').strip()
    page = request.args.get('page', 1, type=int)
    
    query = Guest.query
    
    # Apply search filter matching guest_name, email, or qr_code
    if search:
        query = query.filter((Guest.guest_name.ilike(f"%{search}%")) | (Guest.email.ilike(f"%{search}%")) | (Guest.qr_code.ilike(f"%{search}%")))
        
    # Apply status filter
    if status in ('Sent', 'Email_Sent'):
        query = query.filter(Guest.invite_sent == True)
    elif status in ('Failed', 'Email_Failed'):
        query = query.filter(Guest.invite_sent == False, Guest.remarks.is_not(None))
    elif status in ('Pending', 'Email_Pending'):
        query = query.filter(Guest.invite_sent == False, Guest.remarks.is_(None))
    elif status in ('WhatsApp_Sent', 'WhatsApp_Failed', 'WhatsApp_Pending'):
        import json
        import os
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
        
        if status == 'WhatsApp_Sent':
            query = query.filter(Guest.id.in_(sent_ids)) if sent_ids else query.filter(db.false())
        elif status == 'WhatsApp_Failed':
            query = query.filter(Guest.id.in_(failed_ids)) if failed_ids else query.filter(db.false())
        elif status == 'WhatsApp_Pending':
            all_known_ids = sent_ids + failed_ids
            if all_known_ids:
                query = query.filter(~Guest.id.in_(all_known_ids))

        
    # Apply sorting
    if sort_by == 'name':
        order_col = Guest.guest_name
    elif sort_by == 'email':
        order_col = Guest.email
    elif sort_by == 'code':
        order_col = Guest.qr_code
    elif sort_by == 'status':
        order_col = Guest.invite_sent
    else:
        order_col = Guest.created_at
        
    if sort_dir == 'asc':
        query = query.order_by(order_col.asc())
    else:
        query = query.order_by(order_col.desc())
        
    # Paginate
    pagination = query.paginate(page=page, per_page=10, error_out=False)
    guests = pagination.items
    
    # Lazily generate QR code passes for guests on the current page if they are missing
    import os
    for guest in guests:
        barcode_full_path = ""
        if guest.qr_image:
            barcode_full_path = os.path.join(current_app.root_path, guest.qr_image)
            
        if not guest.qr_image or not os.path.exists(barcode_full_path):
            try:
                from services.barcode_service import BarcodeService
                qr_image_path = BarcodeService.generate_barcode(guest.qr_code)
                guest.qr_image = qr_image_path
                db.session.commit()
            except Exception as e:
                current_app.logger.error(f"Failed to generate QR code dynamically for guest #{guest.id}: {str(e)}")
    
    action_form = EmptyForm() # Form for CSRF validation on action buttons
    
    return render_template(
        'guests/list.html',
        guests=guests,
        pagination=pagination,
        search=search,
        status=status,
        sort_by=sort_by,
        sort_dir=sort_dir,
        action_form=action_form
    )

@guests_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    form = GuestForm()
    if form.validate_on_submit():
        name = form.name.data
        email = form.email.data
        rollno = form.rollno.data
        mobile = form.mobile.data
        try:
            GuestService.create_guest(name, email, rollno=rollno, mobile=mobile)
            flash(f"Guest {name} added successfully!", "success")
            return redirect(url_for('guests.index'))
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            current_app.logger.error(f"Error adding guest manually: {str(e)}")
            flash("An unexpected error occurred while adding guest.", "danger")
            
    return render_template('guests/add_edit.html', form=form, title="Add Guest", is_edit=False)

@guests_bp.route('/<int:guest_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(guest_id):
    guest = Guest.query.get_or_404(guest_id)
    form = GuestForm()
    
    if request.method == 'GET':
        form.name.data = guest.guest_name
        form.email.data = guest.email
        form.rollno.data = guest.rollno
        form.mobile.data = guest.mobile
        
    if form.validate_on_submit():
        name = form.name.data
        email = form.email.data
        rollno = form.rollno.data
        mobile = form.mobile.data
        try:
            GuestService.update_guest(guest_id, name, email, rollno=rollno, mobile=mobile)
            flash(f"Guest {name} updated successfully!", "success")
            return redirect(url_for('guests.index'))
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            current_app.logger.error(f"Error editing guest: {str(e)}")
            flash("An unexpected error occurred while updating guest.", "danger")
            
    return render_template('guests/add_edit.html', form=form, title="Edit Guest", is_edit=True, guest=guest)

@guests_bp.route('/<int:guest_id>/delete', methods=['POST'])
@login_required
def delete(guest_id):
    form = EmptyForm()
    if form.validate_on_submit():
        guest = Guest.query.get_or_404(guest_id)
        name = guest.guest_name
        if GuestService.delete_guest(guest_id):
            flash(f"Guest {name} deleted successfully.", "success")
        else:
            flash(f"Failed to delete guest {name}.", "danger")
    else:
        flash("CSRF token verification failed.", "danger")
    return redirect(url_for('guests.index'))

@guests_bp.route('/<int:guest_id>/regenerate', methods=['POST'])
@login_required
def regenerate(guest_id):
    form = EmptyForm()
    if form.validate_on_submit():
        try:
            guest = GuestService.regenerate_code(guest_id)
            flash(f"Successfully regenerated new invitation code {guest.qr_code} and QR pass for {guest.guest_name}.", "success")
        except Exception as e:
            current_app.logger.error(f"Error regenerating guest code: {str(e)}")
            flash("Failed to regenerate code.", "danger")
    else:
        flash("CSRF token verification failed.", "danger")
    return redirect(url_for('guests.index'))

@guests_bp.route('/<int:guest_id>/toggle_scan', methods=['POST'])
@login_required
def toggle_scan(guest_id):
    form = EmptyForm()
    if form.validate_on_submit():
        from datetime import datetime
        guest = Guest.query.get_or_404(guest_id)
        guest.is_scanned = not guest.is_scanned
        if guest.is_scanned:
            guest.scanned_at = datetime.utcnow()
            guest.last_scanned_at = datetime.utcnow()
        else:
            guest.scanned_at = None
        db.session.commit()
        status_str = "Scanned" if guest.is_scanned else "Not Scanned"
        flash(f"Scan status for {guest.guest_name} has been toggled to {status_str}.", "success")
    else:
        flash("CSRF token verification failed.", "danger")
    return redirect(request.referrer or url_for('guests.index'))
