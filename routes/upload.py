import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session
from flask_login import login_required
from werkzeug.utils import secure_filename

from forms import ExcelUploadForm
from services.excel_service import ExcelService

upload_bp = Blueprint('upload', __name__, url_prefix='/upload')

@upload_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    form = ExcelUploadForm()
    summary = session.pop('import_summary', None)
    
    if form.validate_on_submit():
        file = form.excel_file.data
        filename = secure_filename(file.filename)
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        
        try:
            file.save(file_path)
            
            # Process Excel import
            result = ExcelService.process_import(file_path)
            
            # Remove file after import to keep environment clean
            if os.path.exists(file_path):
                os.remove(file_path)
                
            if result['success']:
                session['import_summary'] = result
                flash(f"Successfully processed spreadsheet. Imported: {result['imported_count']} guests.", "success")
                return redirect(url_for('upload.index'))
            else:
                flash(f"Failed to import spreadsheet: {', '.join(result['errors'])}", "danger")
        except Exception as e:
            current_app.logger.error(f"Excel upload error: {str(e)}")
            flash(f"An error occurred during file upload processing: {str(e)}", "danger")
            if 'file_path' in locals() and os.path.exists(file_path):
                os.remove(file_path)
                
    return render_template('guests/upload.html', form=form, summary=summary)
