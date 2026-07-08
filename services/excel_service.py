import os
import re
from openpyxl import load_workbook
from flask import current_app

from models import db
from models.guest import Guest
from services.guest_service import GuestService

class ExcelService:
    @staticmethod
    def process_import(file_path):
        """
        Parses an Excel spreadsheet, validates columns and data format,
        extracts optional rollno and mobile, generates QR codes, and inserts into event_qr_codes.
        """
        summary = {
            'success': False,
            'imported_count': 0,
            'skipped_duplicates': 0,
            'invalid_emails': 0,
            'errors': [],
            'skipped_details': []
        }
        
        try:
            wb = load_workbook(file_path, read_only=True, data_only=True)
            sheet = wb.active
            
            # Read header row
            rows_iter = sheet.iter_rows(values_only=True)
            try:
                headers = next(rows_iter)
            except StopIteration:
                summary['errors'].append("The Excel sheet is empty.")
                return summary

            # Normalize headers
            if not headers:
                summary['errors'].append("Could not read headers.")
                return summary
                
            headers_clean = [str(h).strip().lower() for h in headers if h is not None]
            
            # Check for required headers
            if len(headers_clean) < 2 or 'name' not in headers_clean or 'email' not in headers_clean:
                summary['errors'].append("Invalid headers. Excel file must contain 'Name' and 'Email' columns.")
                return summary
                
            name_idx = headers_clean.index('name')
            email_idx = headers_clean.index('email')
            
            # Dynamically look up optional rollno and mobile columns
            rollno_idx = None
            for idx, h in enumerate(headers_clean):
                if h in ('rollno', 'roll no', 'roll number', 'roll'):
                    rollno_idx = idx
                    break

            mobile_idx = None
            for idx, h in enumerate(headers_clean):
                if h in ('mobile', 'mobile no', 'mobile number', 'phone', 'phone number'):
                    mobile_idx = idx
                    break
            
            seen_emails = set()
            row_num = 1
            
            for row in rows_iter:
                row_num += 1
                
                # Check if row is empty
                if not row or len(row) <= max(name_idx, email_idx):
                    continue
                    
                name_val = row[name_idx]
                email_val = row[email_idx]
                
                name = str(name_val).strip() if name_val is not None else ""
                email = str(email_val).strip().lower() if email_val is not None else ""
                
                # Skip fully empty rows
                if not name and not email:
                    continue
                
                # Validate name and email are present
                if not name or not email:
                    summary['invalid_emails'] += 1
                    summary['skipped_details'].append({
                        'row': row_num,
                        'name': name or "[Missing]",
                        'email': email or "[Missing]",
                        'reason': "Name or Email is missing"
                    })
                    continue
                
                # Validate email format
                if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                    summary['invalid_emails'] += 1
                    summary['skipped_details'].append({
                        'row': row_num,
                        'name': name,
                        'email': email,
                        'reason': "Invalid email format"
                    })
                    continue
                
                # Check for duplicates within this file
                if email in seen_emails:
                    summary['skipped_duplicates'] += 1
                    summary['skipped_details'].append({
                        'row': row_num,
                        'name': name,
                        'email': email,
                        'reason': "Duplicate email in spreadsheet"
                    })
                    continue
                
                # Check for duplicates in database
                db_guest = Guest.query.filter_by(email=email).first()
                if db_guest:
                    summary['skipped_duplicates'] += 1
                    summary['skipped_details'].append({
                        'row': row_num,
                        'name': name,
                        'email': email,
                        'reason': "Guest email already registered in database"
                    })
                    continue
                
                # Extract optional fields
                rollno = None
                if rollno_idx is not None and len(row) > rollno_idx:
                    rollno_val = row[rollno_idx]
                    rollno = str(rollno_val).strip() if rollno_val is not None else None

                mobile = None
                if mobile_idx is not None and len(row) > mobile_idx:
                    mobile_val = row[mobile_idx]
                    mobile = str(mobile_val).strip() if mobile_val is not None else None
                
                # Add to file set to prevent duplicates inside sheet
                seen_emails.add(email)
                
                # Insert Guest and trigger invitation email
                try:
                    new_guest = GuestService.create_guest(name, email, rollno=rollno, mobile=mobile)
                    
                    # Automatically trigger invitation email dispatch in background
                    from services.email_service import EmailService
                    EmailService.send_invitation_email(new_guest.id)
                    
                    summary['imported_count'] += 1
                except Exception as e:
                    current_app.logger.error(f"Error creating guest on row {row_num}: {str(e)}")
                    summary['skipped_details'].append({
                        'row': row_num,
                        'name': name,
                        'email': email,
                        'reason': f"Database error: {str(e)}"
                    })
            
            wb.close()
            summary['success'] = True
            
        except Exception as e:
            current_app.logger.error(f"Excel reading failed: {str(e)}")
            summary['errors'].append(f"Failed to read spreadsheet file: {str(e)}")
            
        return summary
