from flask import Blueprint, render_template, redirect, url_for, flash, request
from app import db, bcrypt
from app.forms import LoginForm, SetupForm
from app.models import User
from flask_login import login_user, logout_user, login_required, current_user

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if not User.query.first():
        return redirect(url_for('auth.setup'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.index'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', title='Login', form=form)

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))

@auth.route('/setup', methods=['GET', 'POST'])
def setup():
    if User.query.first():
        flash('Setup has already been completed.', 'warning')
        return redirect(url_for('main.index'))
    form = SetupForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Admin account created successfully. You can now log in.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/setup.html', title='Setup', form=form)