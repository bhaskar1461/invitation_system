import os
import json
import ssl
import time
import base64
import urllib.parse
import urllib.request
from datetime import datetime
from flask import current_app
from celery import shared_task

from models import db
from models.guest import Guest

def _normalize_phone(phone_number):
    """Clean and normalize phone number to digits only, with 91 country code."""
    if not phone_number:
        return None
    digits = "".join(c for c in str(phone_number) if c.isdigit())
    if not digits:
        return None
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 10:
        digits = "91" + digits
    return digits

def _build_whatsapp_payload(target_number, guest, base_url, template_id, from_number):
    """
    Build the JSON payload for the SNIST Unified Messaging Platform WhatsApp API.
    Handles the helpdesk template variables if the default 1773697 is used,
    otherwise formats variables for a generic invitation template.
    """
    ticket_url = f"{base_url.rstrip('/')}/ticket/{guest.qr_code}"
    
    # Lazily generate QR code containing the unique 6-digit code if missing
    from flask import current_app
    app = current_app._get_current_object()
    barcode_full_path = ""
    if guest.qr_image:
        barcode_full_path = os.path.join(app.root_path, guest.qr_image)
        
    if not guest.qr_image or not os.path.exists(barcode_full_path):
        try:
            from services.barcode_service import BarcodeService
            qr_image_path = BarcodeService.generate_barcode(guest.qr_code)
            guest.qr_image = qr_image_path
            db.session.commit()
        except Exception as e:
            app.logger.error(f"Failed to generate QR code in WhatsApp payload builder: {str(e)}")

    image_url = f"{base_url.rstrip('/')}/static/barcodes/{guest.qr_code}.png"
    # If running locally, Meta/WhatsApp servers cannot fetch from localhost/127.0.0.1.
    # We fall back to a public placeholder image to ensure message delivery during local testing.
    parsed_url = urllib.parse.urlparse(image_url)
    if parsed_url.hostname in ('localhost', '127.0.0.1') or 'localhost' in image_url:
        image_url = "https://dummyimage.com/600x400/000/fff.png"

    if template_id == "1773697":
        # Dear {{1}}, A new system support ticket has been allocated to you.
        # Ticket ID: {{2}} Category: {{3}} Priority: {{4}} ... {{5}}, Helpdesk.
        template_info = f"{template_id}~{guest.guest_name}~{guest.qr_code}~Invitation~Urgent~{ticket_url}"
        media_type = ""
        content_type = ""
        mediadata_val = ""
        filename_val = ""
        msg_type = "1"
    elif template_id == "1574920":
        # Two variables: name and qr_code
        template_info = f"{template_id}~{guest.guest_name}~{guest.qr_code}"
        media_type = ""
        content_type = ""
        mediadata_val = ""
        filename_val = ""
        msg_type = "1"
    elif template_id in ("1776471", "1776475"):
        # Dear {{1}}, Sreenidhi University cordially invites you to be a part of our Founder's Day celebrations.
        # Header: Image, Body: Dear {{1}}, ...
        template_info = f"{template_id}~{guest.guest_name}"
        media_type = "image"
        content_type = "image/png"
        mediadata_val = image_url
        filename_val = "pass.png"
        msg_type = "3"  # Trans with Media
    else:
        # Custom/Registered invitation template variables
        # Format: templateId~guest_name~qr_code~ticket_url
        template_info = f"{template_id}~{guest.guest_name}~{guest.qr_code}~{ticket_url}"
        media_type = ""
        content_type = ""
        mediadata_val = ""
        filename_val = ""
        msg_type = "1"

    payload = {
        "apiver": "1.0",
        "whatsapp": {
            "ver": "2.0",
            "dlr": {
                "url": ""
            },
            "messages": [
                {
                    "coding": "1",
                    "id": str(guest.id),
                    "msgtype": msg_type,
                    "templateinfo": template_info,
                    "type": media_type,
                    "contenttype": content_type,
                    "b_urlinfo": "",
                    "mediadata": mediadata_val,
                    "filename": filename_val,
                    "text": "",
                    "addresses": [
                        {
                            "seq": "1",
                            "to": str(target_number),
                            "from": str(from_number),
                            "tag": "sreenidhi-invitation"
                        }
                    ]
                }
            ]
        }
    }
    return payload


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_whatsapp_task(self, guest_id, base_url):
    """
    Background worker task to dispatch single WhatsApp messages.
    Automatically runs inside the Flask app context.
    """
    from flask import current_app
    app = current_app._get_current_object()
    
    rate_delay = app.config.get('WHATSAPP_RATE_DELAY', 1.0)
    if rate_delay > 0:
        time.sleep(rate_delay)
        
    guest = Guest.query.get(guest_id)
    if not guest:
        app.logger.warning(f"Async WhatsApp task failed: Guest #{guest_id} not found.")
        return False

    raw_phone = guest.mobile
    target_number = _normalize_phone(raw_phone)
    
    # Check if a global test redirection number is configured
    test_number = app.config.get('WHATSAPP_TEST_NUMBER')
    if test_number:
        target_number = _normalize_phone(test_number)
        
    if not target_number:
        error_msg = f"Invalid/missing mobile number for guest: {raw_phone}"
        app.logger.error(error_msg)
        WhatsAppService._log_outcome(guest, 'Failed', error_msg)
        return False

    provider = app.config.get('WHATSAPP_PROVIDER', 'simulation').lower()
    template_id = app.config.get('WHATSAPP_TEMPLATE_ID', '1773697')
    from_number = app.config.get('WHATSAPP_FROM_NUMBER', '919133386678')
    api_url = app.config.get('WHATSAPP_API_URL', 'https://103.229.250.150/unified/v2/send')

    ticket_url = f"{base_url.rstrip('/')}/ticket/{guest.qr_code}"
    
    # 1. Simulation Mode
    if provider == 'simulation':
        log_dir = os.path.join(app.root_path, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        sim_log_file = os.path.join(log_dir, 'whatsapp_simulation.log')
        
        image_url = f"{base_url.rstrip('/')}/static/barcodes/{guest.qr_code}.png"
        if template_id == "1574920":
            msg_text = f"Dear {guest.guest_name}, custom invitation. QR Code: {guest.qr_code}"
        elif template_id in ("1776471", "1776475"):
            msg_text = f"Dear {guest.guest_name}, Sreenidhi University cordially invites you to be a part of our Founder's Day celebrations. Please find your personalized digital entry pass below. Show this QR code at the entrance for verification. [Header Image: {image_url}]"
        else:
            msg_text = f"Dear {guest.guest_name}, you are cordially invited to Sreenidhi University Founder's Day. Passcode: {guest.qr_code}. View entry pass here: {ticket_url}. - SNIST"
            
        with open(sim_log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n==================================================\n")
            f.write(f"SIMULATION TIME: {datetime.utcnow()}\n")
            f.write(f"TO (ORIGINAL): {raw_phone}\n")
            f.write(f"TO (NORMALIZED): {target_number}\n")
            f.write(f"FROM: {from_number}\n")
            f.write(f"TEMPLATE ID: {template_id}\n")
            f.write(f"GUEST: {guest.guest_name} (Code: {guest.qr_code})\n")
            f.write(f"MESSAGE TEXT: {msg_text}\n")
            f.write(f"==================================================\n")
            
        app.logger.info(f"Simulated WhatsApp sent to {target_number} (logged to whatsapp_simulation.log)")
        WhatsAppService._log_outcome(guest, 'Sent')
        return True

    # 2. Production Mode (Unified Messaging Platform API via Basic Auth)
    payload = _build_whatsapp_payload(target_number, guest, base_url, template_id, from_number)
    json_data = json.dumps(payload).encode("utf-8")

    token = app.config.get('WHATSAPP_TOKEN')
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "SNIST-Invitation-Portal/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        client_id = app.config.get('WHATSAPP_CLIENT_ID', 'sreenidhiclgbepfs44jy504')
        client_password = app.config.get('WHATSAPP_CLIENT_PASSWORD', 'wm84r8yhj9mzp9m1yrm78fqhpmzb8on0')
        credentials = f"{client_id}:{client_password}"
        auth_b64 = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
        headers["Authorization"] = f"Basic {auth_b64}"

    try:
        # Ignore SSL validation for internal/self-signed IP host
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(api_url, data=json_data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as response:
            resp_body = response.read().decode("utf-8")
            app.logger.info(f"WhatsApp API response ({response.status}): {resp_body}")
            
            # Simple check for success status in response body
            # Response typically contains error/success logs
            if "error" in resp_body.lower() or "fail" in resp_body.lower():
                raise RuntimeError(f"API returned error: {resp_body}")
                
        app.logger.info(f"WhatsApp message successfully sent to {target_number}")
        WhatsAppService._log_outcome(guest, 'Sent')
        return True
        
    except Exception as e:
        error_msg = f"WhatsApp API transmission failed: {str(e)}"
        app.logger.error(error_msg)
        
        try:
            self.retry(exc=e)
        except Exception:
            WhatsAppService._log_outcome(guest, 'Failed', f"Max retries exceeded. Error: {error_msg}")
            return False

@shared_task(bind=True)
def send_whatsapp_bulk_task(self, guest_ids, base_url):
    """
    Background worker task to process a list of guest WhatsApp dispatches in throttled batches.
    """
    from flask import current_app
    app = current_app._get_current_object()
    
    batch_limit = app.config.get('WHATSAPP_BATCH_LIMIT', 100)
    rate_delay = app.config.get('WHATSAPP_RATE_DELAY', 1.0)
    
    app.logger.info(f"Starting bulk WhatsApp task for {len(guest_ids)} guests (batch limit: {batch_limit}, rate delay: {rate_delay}s)")
    
    for i in range(0, len(guest_ids), batch_limit):
        batch = guest_ids[i:i + batch_limit]
        app.logger.info(f"Processing batch of {len(batch)} WhatsApp messages ({i} to {i + len(batch)})")
        
        provider = app.config.get('WHATSAPP_PROVIDER', 'simulation').lower()
        template_id = app.config.get('WHATSAPP_TEMPLATE_ID', '1773697')
        from_number = app.config.get('WHATSAPP_FROM_NUMBER', '919133386678')
        api_url = app.config.get('WHATSAPP_API_URL', 'https://103.229.250.150/unified/v2/send')
        test_number = app.config.get('WHATSAPP_TEST_NUMBER')
        
        client_id = app.config.get('WHATSAPP_CLIENT_ID', 'sreenidhiclgbepfs44jy504')
        client_password = app.config.get('WHATSAPP_CLIENT_PASSWORD', 'wm84r8yhj9mzp9m1yrm78fqhpmzb8on0')
        credentials = f"{client_id}:{client_password}"
        auth_b64 = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
        
        ssl_ctx = None
        if provider == 'production':
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
            
        for idx, guest_id in enumerate(batch):
            guest = Guest.query.get(guest_id)
            if not guest:
                continue
                
            if rate_delay > 0 and idx > 0:
                time.sleep(rate_delay)
                
            raw_phone = guest.mobile
            target_number = _normalize_phone(raw_phone)
            if test_number:
                target_number = _normalize_phone(test_number)
                
            if not target_number:
                error_msg = f"Invalid/missing mobile number in bulk send: {raw_phone}"
                app.logger.error(error_msg)
                WhatsAppService._log_outcome(guest, 'Failed', error_msg)
                continue

            ticket_url = f"{base_url.rstrip('/')}/ticket/{guest.qr_code}"
            
            if provider == 'simulation':
                log_dir = os.path.join(app.root_path, 'logs')
                os.makedirs(log_dir, exist_ok=True)
                sim_log_file = os.path.join(log_dir, 'whatsapp_simulation.log')
                
                image_url = f"{base_url.rstrip('/')}/static/barcodes/{guest.qr_code}.png"
                if template_id == "1574920":
                    msg_text = f"Dear {guest.guest_name}, custom invitation. QR Code: {guest.qr_code}"
                elif template_id in ("1776471", "1776475"):
                    msg_text = f"Dear {guest.guest_name}, Sreenidhi University cordially invites you to be a part of our Founder's Day celebrations. Please find your personalized digital entry pass below. Show this QR code at the entrance for verification. [Header Image: {image_url}]"
                else:
                    msg_text = f"Dear {guest.guest_name}, you are cordially invited to Sreenidhi University Founder's Day. Passcode: {guest.qr_code}. View entry pass here: {ticket_url}. - SNIST"
                    
                with open(sim_log_file, 'a', encoding='utf-8') as f:
                    f.write(f"\n==================================================\n")
                    f.write(f"SIMULATION TIME: {datetime.utcnow()}\n")
                    f.write(f"TO (ORIGINAL): {raw_phone}\n")
                    f.write(f"TO (NORMALIZED): {target_number}\n")
                    f.write(f"FROM: {from_number}\n")
                    f.write(f"TEMPLATE ID: {template_id}\n")
                    f.write(f"GUEST: {guest.guest_name} (Code: {guest.qr_code})\n")
                    f.write(f"MESSAGE TEXT: {msg_text}\n")
                    f.write(f"==================================================\n")
                    
                app.logger.info(f"Simulated WhatsApp sent to {target_number} (logged to whatsapp_simulation.log)")
                WhatsAppService._log_outcome(guest, 'Sent')
                continue
                
            # Production send
            payload = _build_whatsapp_payload(target_number, guest, base_url, template_id, from_number)
            json_data = json.dumps(payload).encode("utf-8")
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Basic {auth_b64}",
                "User-Agent": "SNIST-Invitation-Portal/1.0",
            }
            
            try:
                req = urllib.request.Request(api_url, data=json_data, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as response:
                    resp_body = response.read().decode("utf-8")
                    if "error" in resp_body.lower() or "fail" in resp_body.lower():
                        raise RuntimeError(f"API returned error: {resp_body}")
                app.logger.info(f"WhatsApp sent successfully to {target_number} (bulk)")
                WhatsAppService._log_outcome(guest, 'Sent')
            except Exception as e:
                error_msg = f"WhatsApp bulk transmission failed: {str(e)}"
                app.logger.error(error_msg)
                WhatsAppService._log_outcome(guest, 'Failed', error_msg)
                
    return True

class WhatsAppService:
    @staticmethod
    def send_invitation_whatsapp(guest_id, base_url=None):
        """
        Asynchronously sends a personalized WhatsApp invitation to the guest.
        Delegates the task to Celery background workers.
        """
        app = current_app._get_current_object()
        
        if not base_url:
            from flask import has_request_context, request
            if has_request_context():
                base_url = request.host_url
            else:
                base_url = app.config.get('BASE_URL', 'http://localhost:5000')

        send_whatsapp_task.delay(guest_id, base_url)
        return True, "WhatsApp dispatch task queued successfully"

    @staticmethod
    def send_bulk_invitations(guest_ids, base_url=None):
        """
        Asynchronously sends personalized WhatsApp invitations in bulk.
        Delegates the task to Celery background worker.
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
                
        send_whatsapp_bulk_task.delay(guest_ids, base_url)
        return True, "Bulk WhatsApp dispatch task queued successfully"

    @staticmethod
    def _log_outcome(guest, status, error_message=None):
        """
        Helper method to log WhatsApp sending status to JSON file and update tracking maps.
        """
        import json
        import os
        from flask import current_app, g
        
        try:
            status_file = os.path.join(current_app.instance_path, 'whatsapp_status.json')
            os.makedirs(os.path.dirname(status_file), exist_ok=True)
            
            # Load current data
            data = {}
            if os.path.exists(status_file):
                try:
                    with open(status_file, 'r') as f:
                        data = json.load(f)
                except Exception:
                    data = {}
                    
            # Update guest entry
            if status == 'Sent':
                data[str(guest.id)] = {'sent': True, 'remarks': None}
            else:
                data[str(guest.id)] = {'sent': False, 'remarks': error_message}
                
            # Save back
            with open(status_file, 'w') as f:
                json.dump(data, f)
                
            # Update g cache if available
            if hasattr(g, 'whatsapp_statuses'):
                g.whatsapp_statuses = data
        except Exception as e:
            current_app.logger.error(f"Error logging WhatsApp outcome: {str(e)}")

