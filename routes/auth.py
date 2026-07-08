from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse

from forms import LoginForm
from services.auth_service import AuthService

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
        
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        
        user = AuthService.authenticate_user(email, password)
        if user:
            login_user(user)
            current_app.logger.info(f"User {email} logged in successfully.")
            flash('Logged in successfully!', 'success')
            
            # Safe redirection to prevent Open Redirect vulnerabilities
            next_page = request.args.get('next')
            if not next_page or urlparse(next_page).netloc != '':
                next_page = url_for('dashboard.index')
            return redirect(next_page)
        else:
            current_app.logger.warning(f"Failed login attempt for email: {email}")
            flash('Invalid email or password.', 'danger')
            
    return render_template('login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    email = current_user.email
    logout_user()
    current_app.logger.info(f"User {email} logged out.")
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
