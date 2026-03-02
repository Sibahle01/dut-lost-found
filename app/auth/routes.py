import secrets
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app import db, mail
from app.models.user import User
from flask_mail import Message

# Import the blueprint from the package
from app.auth import bp


# -- REGISTER ------------------------------------------------------------------
@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('items.index'))

    if request.method == 'POST':
        name           = request.form.get('name', '').strip()
        email          = request.form.get('email', '').strip().lower()
        student_number = request.form.get('student_number', '').strip()
        campus         = request.form.get('campus', '').strip()
        password       = request.form.get('password', '')
        confirm        = request.form.get('confirm_password', '')

        # -- Validation ----------------------------------------------------
        errors = []

        if not name:
            errors.append('Full name is required.')

        if not User.is_dut_email(email):
            errors.append('You must register with a DUT email address (@dut.ac.za or @dut4life.ac.za).')

        if User.query.filter_by(email=email).first():
            errors.append('An account with this email already exists.')

        if len(password) < 8:
            errors.append('Password must be at least 8 characters.')

        if password != confirm:
            errors.append('Passwords do not match.')

        if campus not in ['Steve Biko', 'Ritson', 'ML Sultan']:
            errors.append('Please select a valid campus.')

        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('auth/register.html',
                                 form_data=request.form)

        # -- Create User ---------------------------------------------------
        verification_token = secrets.token_urlsafe(32)

        user = User(
            name=name,
            email=email,
            student_number=student_number if student_number else None,
            campus=campus,
            role='student',
            is_verified=True,  # Auto-verified for development
            verification_token=verification_token
        )
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        # -- Email verification disabled for development ------------------
        # Uncomment this block when email sending is configured
        """
        verify_url = url_for('auth.verify_email',
                           token=verification_token, _external=True)
        try:
            msg = Message(
                subject='Verify your DUT Lost & Found account',
                recipients=[email],
                html=f'''
                <h2>Welcome to the DUT Lost & Found Portal</h2>
                <p>Hi {name},</p>
                <p>Please verify your email address to activate your account.</p>
                <p>
                    <a href="{verify_url}"
                       style="background:#C8102E;color:white;padding:12px 24px;
                              text-decoration:none;border-radius:4px;">
                        Verify My Account
                    </a>
                </p>
                <p>Or copy this link: {verify_url}</p>
                <p>This link does not expire, but your account cannot be used
                   until it is verified.</p>
                <br>
                <small>DUT Lost &amp; Found Portal — Durban University of Technology</small>
                '''
            )
            mail.send(msg)
            flash('Account created! Please check your email to verify your account '
                  'before logging in.', 'success')
        except Exception as e:
            print(f"Email error: {e}")
            flash('Account created, but we could not send a verification email. '
                  'Please contact the administrator.', 'warning')
        """
        
        # Simple success message for development
        flash('Account created successfully! You can now log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', form_data={})


# -- VERIFY EMAIL --------------------------------------------------------------
@bp.route('/verify/<token>')
def verify_email(token):
    user = User.query.filter_by(verification_token=token).first()

    if not user:
        flash('Invalid or expired verification link.', 'danger')
        return redirect(url_for('auth.login'))

    if user.is_verified:
        flash('Your account is already verified. Please log in.', 'info')
        return redirect(url_for('auth.login'))

    user.is_verified = True
    user.verification_token = None
    db.session.commit()

    flash('Email verified successfully. You can now log in.', 'success')
    return redirect(url_for('auth.login'))


# -- LOGIN ---------------------------------------------------------------------
@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('items.index'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember_me') == 'on'

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash('Invalid email or password.', 'danger')
            return render_template('auth/login.html', email=email)

        # This check will now pass because users are auto-verified
        if not user.is_verified:
            flash('Please verify your email address before logging in. '
                  'Check your inbox for the verification link.', 'warning')
            return render_template('auth/login.html', email=email)

        login_user(user, remember=remember)

        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        if user.is_admin:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('claims.dashboard'))

    return render_template('auth/login.html', email='')


# -- LOGOUT --------------------------------------------------------------------
@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))