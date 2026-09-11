# app/routes/synology.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from wtforms.validators import Optional
from ..extensions import db
from ..models import SynologyDevice, BackupHistory
from ..forms import SynologyDeviceForm
from ..services.synology_service import SynologyService, MockSynologyService
from ..services.backup_sync_service import BackupSyncService
from ..extensions import csrf

synology_bp = Blueprint('synology', __name__)

@synology_bp.route('/')
@login_required
def index():
    devices = SynologyDevice.query.all()
    return render_template('synology/index.html', devices=devices)

@synology_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if not current_user.is_admin():
        flash('Admin access required.', 'danger')
        return redirect(url_for('synology.index'))
    form = SynologyDeviceForm()
    if form.validate_on_submit():
        try:
            device = SynologyDevice(
                name=form.name.data,
                host=form.host.data,
                port=form.port.data,
                protocol=form.protocol.data,
                username=form.username.data,
                verify_ssl=form.verify_ssl.data,
                is_active=form.is_active.data
            )
            if form.password.data:
                device.password = form.password.data
            db.session.add(device)
            db.session.commit()
            flash('Synology device added.', 'success')
            return redirect(url_for('synology.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    return render_template('synology/create.html', form=form)

@synology_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    if not current_user.is_admin():
        flash('Admin access required.', 'danger')
        return redirect(url_for('synology.index'))
    device = SynologyDevice.query.get_or_404(id)
    form = SynologyDeviceForm(obj=device)
    if form.validate_on_submit():
        try:
            device.name = form.name.data
            device.host = form.host.data
            device.port = form.port.data
            device.protocol = form.protocol.data
            device.username = form.username.data
            if form.password.data:
                device.password = form.password.data
            device.verify_ssl = form.verify_ssl.data
            device.is_active = form.is_active.data
            db.session.commit()
            flash('Synology device updated.', 'success')
            return redirect(url_for('synology.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    # Untuk edit, password tidak wajib diisi, dan kita tidak tampilkan password terenkripsi
    form.password.validators = [Optional()]
    return render_template('synology/edit.html', form=form, device=device)

@synology_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    if not current_user.is_admin():
        flash('Admin access required.', 'danger')
        return redirect(url_for('synology.index'))
    device = SynologyDevice.query.get_or_404(id)
    try:
        db.session.delete(device)
        db.session.commit()
        flash('Device deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting: {str(e)}', 'danger')
    return redirect(url_for('synology.index'))

@synology_bp.route('/<int:id>/test', methods=['POST'])
@login_required
def test_connection(id):
    device = SynologyDevice.query.get_or_404(id)
    # Use real or mock based on config? We'll use real by default
    service = SynologyService(device)
    result = service.test_connection()
    return jsonify(result)

@synology_bp.route('/<int:id>/sync', methods=['POST'])
@login_required
def sync_now(id):
    device = SynologyDevice.query.get_or_404(id)
    sync_service = BackupSyncService(use_mock=False)  # or use_mock based on env
    result = sync_service.sync_device(device)
    if result['status'] == 'SUCCESS':
        flash(f"Sync completed for {device.name}: {result['records_created']} new, {result['records_updated']} updated.", 'success')
    else:
        flash(f"Sync failed for {device.name}: {result.get('error', 'Unknown error')}", 'danger')
    return redirect(url_for('synology.index'))