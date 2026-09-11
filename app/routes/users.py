from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from ..extensions import db
from ..models import User
from ..forms import UserForm

users_bp = Blueprint('users', __name__)

@users_bp.route('/')
@login_required
def index():
    if not current_user.is_admin():
        flash('Admin access required.', 'danger')
        return redirect(url_for('dashboard.index'))
    users = User.query.all()
    return render_template('users/index.html', users=users)

@users_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if not current_user.is_admin():
        flash('Admin access required.', 'danger')
        return redirect(url_for('dashboard.index'))
    form = UserForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data, role=form.role.data, is_active=form.is_active.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('User created.', 'success')
        return redirect(url_for('users.index'))
    return render_template('users/create.html', form=form)

@users_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    if not current_user.is_admin():
        flash('Admin access required.', 'danger')
        return redirect(url_for('dashboard.index'))
    user = User.query.get_or_404(id)
    form = UserForm(obj=user)
    if form.validate_on_submit():
        user.username = form.username.data
        user.email = form.email.data
        user.role = form.role.data
        user.is_active = form.is_active.data
        if form.password.data:
            user.set_password(form.password.data)
        db.session.commit()
        flash('User updated.', 'success')
        return redirect(url_for('users.index'))
    return render_template('users/edit.html', form=form, user=user)

@users_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    if not current_user.is_admin():
        flash('Admin access required.', 'danger')
        return redirect(url_for('dashboard.index'))
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash('Cannot delete yourself.', 'danger')
        return redirect(url_for('users.index'))
    db.session.delete(user)
    db.session.commit()
    flash('User deleted.', 'success')
    return redirect(url_for('users.index'))