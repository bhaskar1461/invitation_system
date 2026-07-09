import os
import smtplib
from datetime import datetime
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from flask import current_app, render_template
from celery import shared_task

from models import db
from models.guest import Guest

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_invitation_task(self, guest_id, base_url):
    """
    Background worker task to process email dispatches.
    It automatically runs inside the Flask app context.
    """
    from flask import current_app
    app = current_app._get_current_object()
    
    # Retrieve configuration limits/throttling
    rate_delay = app.config.get('SMTP_RATE_DELAY', 1.0)
    
    # Process delay to throttle SMTP dispatches
    if rate_delay > 0:
        time.sleep(rate_delay)
        
    guest = Guest.query.get(guest_id)
    if not guest:
        app.logger.warning(f"Async email task failed: Guest #{guest_id} not found.")
        return False

    sender = app.config['SMTP_SENDER']
    recipient = guest.email
    subject = f"Official Invitation: Sreenidhi University Founder's Day"

    # 0. Lazily generate QR code containing the unique 6-digit code if missing
    barcode_full_path = ""
    if guest.qr_image:
        barcode_full_path = os.path.join(app.root_path, guest.qr_image)
        
    if not guest.qr_image or not os.path.exists(barcode_full_path):
        try:
            from services.barcode_service import BarcodeService
            # This will overlay the QR code containing the 6-digit code onto the template poster
            qr_image_path = BarcodeService.generate_barcode(guest.qr_code)
            guest.qr_image = qr_image_path
            db.session.commit()
            barcode_full_path = os.path.join(app.root_path, guest.qr_image)
        except Exception as e:
            error_msg = f"Failed to generate QR code: {str(e)}"
            app.logger.error(error_msg)
            EmailService._log_outcome(guest, 'Failed', error_msg)
            return False

    # 1. Render the HTML email content
    try:
        html_content = render_template(
            'emails/invitation.html',
            guest=guest,
            event_name="Sreenidhi University Founder's Day",
            event_date="10th July 2026",
            event_time="5:30 PM onwards",
            event_venue="Sreenidhi University Campus"
        )
    except Exception as e:
        error_msg = f"Template rendering failed: {str(e)}"
        app.logger.error(error_msg)
        EmailService._log_outcome(guest, 'Failed', error_msg)
        return False

    # 2. Check if we are running in simulation mode
    if app.config['SMTP_HOST'] == 'simulation' or not app.config['SMTP_HOST']:
        log_dir = os.path.join(app.root_path, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        sim_log_file = os.path.join(log_dir, 'email_simulation.log')
        
        with open(sim_log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n==================================================\n")
            f.write(f"SIMULATION TIME: {datetime.utcnow()}\n")
            f.write(f"FROM: {sender}\n")
            f.write(f"TO: {recipient}\n")
            f.write(f"SUBJECT: {subject}\n")
            f.write(f"GUEST: {guest.guest_name} (Code: {guest.qr_code})\n")
            f.write(f"BARCODE/QR PATH: {barcode_full_path}\n")
            f.write(f"--- HTML CONTENT ---\n")
            f.write(html_content)
            f.write(f"\n==================================================\n")
            
        app.logger.info(f"Simulated email sent to {recipient} (logged to email_simulation.log)")
        EmailService._log_outcome(guest, 'Sent')
        return True

    # 3. Setup MIME message
    msg = MIMEMultipart('related')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient

    # Attach HTML body
    msg_alternative = MIMEMultipart('alternative')
    msg.attach(msg_alternative)
    msg_html = MIMEText(html_content, 'html', 'utf-8')
    msg_alternative.attach(msg_html)

    # Attach QR Image inline
    if os.path.exists(barcode_full_path):
        try:
            with open(barcode_full_path, 'rb') as img_f:
                msg_image = MIMEImage(img_f.read())
                msg_image.add_header('Content-ID', '<barcode_image>')
                msg_image.add_header('Content-Disposition', 'inline', filename=os.path.basename(barcode_full_path))
                msg.attach(msg_image)
        except Exception as e:
            error_msg = f"Failed to attach QR image: {str(e)}"
            app.logger.error(error_msg)
            EmailService._log_outcome(guest, 'Failed', error_msg)
            return False
    else:
        error_msg = f"QR image file not found at {barcode_full_path}"
        app.logger.error(error_msg)
        EmailService._log_outcome(guest, 'Failed', error_msg)
        return False

    # 4. Connect to SMTP server and send with retry limits
    try:
        server = smtplib.SMTP(app.config['SMTP_HOST'], app.config['SMTP_PORT'], timeout=10)
        if app.config['SMTP_USE_TLS']:
            server.starttls()
        
        # Auth if credentials provided
        username = app.config['SMTP_USER']
        password = app.config['SMTP_PASSWORD']
        if username and password:
            server.login(username, password)
            
        server.sendmail(sender, [recipient], msg.as_string())
        server.quit()
        
        app.logger.info(f"Email sent successfully to {recipient}")
        EmailService._log_outcome(guest, 'Sent')
        return True
        
    except Exception as e:
        error_msg = f"SMTP transmission failed: {str(e)}"
        app.logger.error(error_msg)
        
        # Attempt backoff retry using Celery's built-in retry functionality
        try:
            self.retry(exc=e)
        except Exception as retry_exc:
            # Reached max retries, log failure to database
            EmailService._log_outcome(guest, 'Failed', f"Max retries exceeded. Error: {error_msg}")
            return False

@shared_task(bind=True)
def send_invitations_bulk_task(self, guest_ids, base_url):
    """
    Background worker task to process a list of guest emails in batches using a persistent SMTP session.
    """
    from flask import current_app
    app = current_app._get_current_object()
    
    batch_limit = app.config.get('SMTP_BATCH_LIMIT', 100)
    rate_delay = app.config.get('SMTP_RATE_DELAY', 1.0)
    
    app.logger.info(f"Starting bulk email task for {len(guest_ids)} guests (batch limit: {batch_limit}, rate delay: {rate_delay}s)")
    
    # Split guest_ids into batches of batch_limit
    for i in range(0, len(guest_ids), batch_limit):
        batch = guest_ids[i:i + batch_limit]
        app.logger.info(f"Processing batch of {len(batch)} emails ({i} to {i + len(batch)})")
        
        is_simulation = app.config['SMTP_HOST'] == 'simulation' or not app.config['SMTP_HOST']
        server = None
        
        if not is_simulation:
            try:
                server = smtplib.SMTP(app.config['SMTP_HOST'], app.config['SMTP_PORT'], timeout=15)
                if app.config['SMTP_USE_TLS']:
                    server.starttls()
                username = app.config['SMTP_USER']
                password = app.config['SMTP_PASSWORD']
                if username and password:
                    server.login(username, password)
            except Exception as e:
                error_msg = f"SMTP connection failed for batch: {str(e)}"
                app.logger.error(error_msg)
                # Mark all guests in this batch as failed
                for g_id in batch:
                    guest = Guest.query.get(g_id)
                    if guest:
                        EmailService._log_outcome(guest, 'Failed', error_msg)
                continue
                
        # Send emails to guests in current batch
        for idx, guest_id in enumerate(batch):
            guest = Guest.query.get(guest_id)
            if not guest:
                continue
                
            # Throttling delay between sending individual emails in the same SMTP session
            if rate_delay > 0 and idx > 0:
                time.sleep(rate_delay)
                
            # Lazily generate QR code containing the unique 6-digit code if missing
            barcode_full_path = ""
            if guest.qr_image:
                barcode_full_path = os.path.join(app.root_path, guest.qr_image)
                
            if not guest.qr_image or not os.path.exists(barcode_full_path):
                try:
                    from services.barcode_service import BarcodeService
                    qr_image_path = BarcodeService.generate_barcode(guest.qr_code)
                    guest.qr_image = qr_image_path
                    db.session.commit()
                    barcode_full_path = os.path.join(app.root_path, guest.qr_image)
                except Exception as e:
                    error_msg = f"Failed to generate QR code in bulk send: {str(e)}"
                    app.logger.error(error_msg)
                    EmailService._log_outcome(guest, 'Failed', error_msg)
                    continue
                    
            sender = app.config['SMTP_SENDER']
            recipient = guest.email
            subject = f"Official Invitation: Sreenidhi University Founder's Day"
            
            # Render templates
            try:
                html_content = render_template(
                    'emails/invitation.html',
                    guest=guest,
                    event_name="Sreenidhi University Founder's Day",
                    event_date="10th July 2026",
                    event_time="5:30 PM onwards",
                    event_venue="Sreenidhi University Campus"
                )
            except Exception as e:
                error_msg = f"Template rendering failed: {str(e)}"
                app.logger.error(error_msg)
                EmailService._log_outcome(guest, 'Failed', error_msg)
                continue
                
            if is_simulation:
                log_dir = os.path.join(app.root_path, 'logs')
                os.makedirs(log_dir, exist_ok=True)
                sim_log_file = os.path.join(log_dir, 'email_simulation.log')
                
                with open(sim_log_file, 'a', encoding='utf-8') as f:
                    f.write(f"\n==================================================\n")
                    f.write(f"SIMULATION TIME: {datetime.utcnow()}\n")
                    f.write(f"FROM: {sender}\n")
                    f.write(f"TO: {recipient}\n")
                    f.write(f"SUBJECT: {subject}\n")
                    f.write(f"GUEST: {guest.guest_name} (Code: {guest.qr_code})\n")
                    f.write(f"BARCODE/QR PATH: {barcode_full_path}\n")
                    f.write(f"--- HTML CONTENT ---\n")
                    f.write(html_content)
                    f.write(f"\n==================================================\n")
                    
                app.logger.info(f"Simulated email sent to {recipient} (logged to email_simulation.log)")
                EmailService._log_outcome(guest, 'Sent')
                continue
                
            # Setup MIME message
            msg = MIMEMultipart('related')
            msg['Subject'] = subject
            msg['From'] = sender
            msg['To'] = recipient
            
            msg_alternative = MIMEMultipart('alternative')
            msg.attach(msg_alternative)
            msg_html = MIMEText(html_content, 'html', 'utf-8')
            msg_alternative.attach(msg_html)
            
            # Attach QR Image inline
            if os.path.exists(barcode_full_path):
                try:
                    with open(barcode_full_path, 'rb') as img_f:
                        msg_image = MIMEImage(img_f.read())
                        msg_image.add_header('Content-ID', '<barcode_image>')
                        msg_image.add_header('Content-Disposition', 'inline', filename=os.path.basename(barcode_full_path))
                        msg.attach(msg_image)
                except Exception as e:
                    error_msg = f"Failed to attach QR image: {str(e)}"
                    app.logger.error(error_msg)
                    EmailService._log_outcome(guest, 'Failed', error_msg)
                    continue
            else:
                error_msg = f"QR image file not found at {barcode_full_path}"
                app.logger.error(error_msg)
                EmailService._log_outcome(guest, 'Failed', error_msg)
                continue
                
            try:
                server.sendmail(sender, [recipient], msg.as_string())
                app.logger.info(f"Email sent successfully to {recipient} (bulk batch)")
                EmailService._log_outcome(guest, 'Sent')
            except Exception as e:
                error_msg = f"SMTP transmission failed in bulk: {str(e)}"
                app.logger.error(error_msg)
                EmailService._log_outcome(guest, 'Failed', error_msg)
                
        if server:
            try:
                server.quit()
            except Exception:
                pass
                
    return True

class EmailService:
    @staticmethod
    def send_invitation_email(guest_id, base_url=None):
        """
        Asynchronously sends a personalized invitation email to the guest.
        Delegates the task to Celery background workers.
        """
        app = current_app._get_current_object()
        
        # Capture base URL from request context or config
        if not base_url:
            from flask import has_request_context, request
            if has_request_context():
                base_url = request.host_url
            else:
                base_url = app.config.get('BASE_URL', 'http://localhost:5000')

        # Trigger Celery background task instead of spawning raw thread
        send_invitation_task.delay(guest_id, base_url)
        return True, "Email dispatch task queued successfully"

    @staticmethod
    def send_bulk_invitations(guest_ids, base_url=None):
        """
        Asynchronously sends personalized invitation emails in bulk.
        Delegates the task to Celery background worker with persistent SMTP sessions.
        """
        if not guest_ids:
            return True, "No guests to process"
            
        app = current_app._get_current_object()
        
        if not base_url:
            from flask import has_request_context, request
            if has_request_context():
                base_url = request.host_url
            else:
                base_url = app.config.get('BASE_URL', 'http://localhost:5000')
                
        # Trigger Celery background task
        send_invitations_bulk_task.delay(guest_ids, base_url)
        return True, "Bulk email dispatch task queued successfully"

    @staticmethod
    def _log_outcome(guest, status, error_message=None):
        """
        Helper method to log sending status to database and update tracking columns.
        """
        if status == 'Sent':
            guest.invite_sent = True
            guest.status = 'ACTIVE'
            guest.remarks = None
        else:
            guest.invite_sent = False
            guest.remarks = error_message
            
        db.session.commit()
