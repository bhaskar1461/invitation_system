import os
import qrcode
from PIL import Image
from flask import current_app

class BarcodeService:
    @staticmethod
    def generate_barcode(code):
        """
        Generates a QR code for the given code and overlays it on the event poster image.
        Saves the compiled PNG under static/barcodes/<code>.png.
        Returns the relative path.
        """
        try:
            folder = current_app.config['BARCODE_FOLDER']
            root_dir = current_app.root_path
        except RuntimeError:
            folder = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'static', 'barcodes')
            root_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..')

        os.makedirs(folder, exist_ok=True)
        
        # 1. Generate QR Code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=0,
        )
        qr.add_data(code)
        qr.make(fit=True)
        
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_img = qr_img.resize((72, 72), Image.Resampling.LANCZOS)
        
        # 2. Overlay onto the base invitation poster
        base_image_path = os.path.join(root_dir, 'static', 'images', 'founders_day_invite.png')
        file_base_path = os.path.join(folder, code)
        
        if os.path.exists(base_image_path):
            try:
                base_img = Image.open(base_image_path).convert("RGBA")
                # Paste the QR code at the scanned coordinates: x=225, y=938
                base_img.paste(qr_img, (225, 938))
                
                final_img = base_img.convert("RGB")
                final_img.save(file_base_path + ".png", "PNG")
            except Exception as e:
                # Fallback to saving raw QR code if overlay operation fails
                qr_img.convert("RGB").save(file_base_path + ".png", "PNG")
        else:
            # Fallback to saving raw QR code if base image not found
            qr_img.convert("RGB").save(file_base_path + ".png", "PNG")
            
        relative_path = f"static/barcodes/{code}.png"
        return relative_path
