import os
import random
import re
from models import db
from models.guest import Guest
from services.barcode_service import BarcodeService

class GuestService:
    @staticmethod
    def generate_unique_code():
        """
        Generates a unique 6-digit numeric code.
        """
        for _ in range(10): # 10 retries for collisions
            code = str(random.randint(100000, 999999))
            existing = Guest.query.filter_by(qr_code=code).first()
            if not existing:
                return code
        raise RuntimeError("Failed to generate a unique 6-digit code after 10 attempts.")

    @staticmethod
    def create_guest(name, email, rollno=None, mobile=None):
        """
        Creates a new guest, generates code, barcode overlay, and audit/visibility fields.
        """
        if not name or not email:
            raise ValueError("Name and Email are required.")
            
        email = email.strip().lower()
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            raise ValueError(f"Invalid email address: {email}")

        # Duplicate check
        existing = Guest.query.filter_by(email=email).first()
        if existing:
            raise ValueError(f"Guest with email {email} already exists.")

        # Generate unique code
        code = GuestService.generate_unique_code()

        # Create Guest in event_qr_codes table with qr_image as None (generated lazily)
        guest = Guest(
            guest_name=name.strip(),
            rollno=rollno.strip() if rollno else "",
            mobile=mobile.strip() if mobile else "",
            email=email,
            qr_code=code,
            qr_image=None,
            invite_sent=False,
            status='ACTIVE'
        )
        db.session.add(guest)
        db.session.commit()

        return guest

    @staticmethod
    def update_guest(guest_id, name, email, rollno=None, mobile=None):
        """
        Updates guest details and records the editor ID.
        """
        guest = Guest.query.get(guest_id)
        if not guest:
            raise ValueError("Guest not found.")

        if not name or not email:
            raise ValueError("Name and Email are required.")

        email = email.strip().lower()
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            raise ValueError(f"Invalid email address: {email}")

        # Duplicate check excluding self
        existing = Guest.query.filter(Guest.email == email, Guest.id != guest_id).first()
        if existing:
            raise ValueError(f"Another guest with email {email} already exists.")

        guest.guest_name = name.strip()
        guest.email = email
        guest.rollno = rollno.strip() if rollno else ""
        guest.mobile = mobile.strip() if mobile else ""
        
        db.session.commit()
        return guest

    @staticmethod
    def delete_guest(guest_id):
        """
        Deletes a guest and removes their invitation pass image.
        """
        guest = Guest.query.get(guest_id)
        if not guest:
            return False

        # Remove barcode/QR file if it exists
        if guest.qr_image:
            full_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', guest.qr_image)
            if os.path.exists(full_path):
                try:
                    os.remove(full_path)
                except Exception:
                    pass

        db.session.delete(guest)
        db.session.commit()

        return True

    @staticmethod
    def regenerate_code(guest_id):
        """
        Regenerates unique code and barcode/QR overlay for an existing guest.
        """
        guest = Guest.query.get(guest_id)
        if not guest:
            raise ValueError("Guest not found.")

        # Remove old QR pass file
        if guest.qr_image:
            full_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', guest.qr_image)
            if os.path.exists(full_path):
                try:
                    os.remove(full_path)
                except Exception:
                    pass

        # Generate new code and barcode
        new_code = GuestService.generate_unique_code()
        qr_image_path = BarcodeService.generate_barcode(new_code)

        guest.qr_code = new_code
        guest.qr_image = qr_image_path
        
        db.session.commit()
        return guest
