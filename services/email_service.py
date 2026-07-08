import os
import smtplib
from datetime import datetime
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from flask import current_app, render_template

from models import db
from models.guest import Guest
from models.email_log import EmailLog

class EmailService:
    @staticmethod
    def send_invitation_email(guest_id, base_url=None):
        """
        Asynchronously sends a personalized invitation email to the guest.
        Spawns a background thread to prevent blocking the web worker.
        """
        app = current_app._get_current_object()
        
        # Capture base URL from request context or config before starting background thread
        if not base_url:
            from flask import has_request_context, request
            if has_request_context():
                base_url = request.host_url
            else:
                base_url = app.config.get('BASE_URL', 'http://localhost:5000')

        thread = threading.Thread(
            target=EmailService._send_invitation_thread,
            args=(app, guest_id, base_url)
        )
        thread.start()
        return True, "Email dispatch initiated in background"

    @staticmethod
    def _send_invitation_thread(app, guest_id, base_url):
        """
        Runs in background thread, utilizing application context.
        """
        with app.app_context():
            guest = Guest.query.get(guest_id)
            if not guest:
                app.logger.warning(f"Async email thread failed: Guest #{guest_id} not found.")
                return

            sender = app.config['SMTP_SENDER']
            recipient = guest.email
            subject = f"Official Invitation: Sreenidhi University Founder's Day"

            # 0. Generate or regenerate QR code containing only the unique verification code
            try:
                from services.barcode_service import BarcodeService
                # This will overlay the QR code containing guest.qr_code onto the template poster
                qr_image_path = BarcodeService.generate_barcode(guest.qr_code)
                guest.qr_image = qr_image_path
                db.session.commit()
            except Exception as e:
                error_msg = f"Failed to generate QR code: {str(e)}"
                app.logger.error(error_msg)
                EmailService._log_outcome(guest, 'Failed', error_msg)
                return

            # Determine full barcode/QR image path
            barcode_rel_path = guest.qr_image
            if not barcode_rel_path:
                EmailService._log_outcome(guest, 'Failed', "No QR image path stored on guest record.")
                return
                
            barcode_full_path = os.path.join(app.root_path, barcode_rel_path)

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
                return

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
                return

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
                    return
            else:
                error_msg = f"QR image file not found at {barcode_full_path}"
                app.logger.error(error_msg)
                EmailService._log_outcome(guest, 'Failed', error_msg)
                return

            # 4. Connect to SMTP server and send
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
                
            except Exception as e:
                error_msg = f"SMTP transmission failed: {str(e)}"
                app.logger.error(error_msg)
                EmailService._log_outcome(guest, 'Failed', error_msg)

    @staticmethod
    def _log_outcome(guest, status, error_message=None):
        """
        Helper method to log sending status to database and update tracking columns.
        """
        guest.email_status = status
        guest.email_retry_count = (guest.email_retry_count or 0) + 1
        
        if status == 'Sent':
            guest.invite_sent = True
            guest.email_sent_at = datetime.utcnow()
            guest.last_email_error = None
        else:
            guest.last_email_error = error_message
            
        log = EmailLog(
            guest_id=guest.id,
            sent_at=datetime.utcnow(),
            status=status,
            error_message=error_message
        )
        db.session.add(log)
        db.session.commit()
