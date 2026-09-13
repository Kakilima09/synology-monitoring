from flask import Blueprint, render_template, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func
from datetime import datetime, timedelta

from ..extensions import db
from ..models import SynologyDevice
from ..models.drive_client import DriveClient
from ..models.drive_log import DriveLog
from ..services.drive_sync_service import DriveSyncService


drive_dashboard_bp = Blueprint('drive_dashboard', __name__, url_prefix='/drive')


@drive_dashboard_bp.route('/')
@login_required
def index():
    # Statistik clients
    total_clients = DriveClient.query.count()
    online_clients = DriveClient.query.filter(
        DriveClient.client_status == 'on_line'
    ).count()
    syncing_clients = DriveClient.query.filter(
        DriveClient.client_status == 'syncing'
    ).count()
    offline_clients = DriveClient.query.filter(
        DriveClient.client_status == 'off_line'
    ).count()

    # Statistik logs
    total_logs = DriveLog.query.count()
    today = func.date(func.now())
    logs_today = DriveLog.query.filter(
        func.date(DriveLog.event_time) == today
    ).count()

    # Recent logs & clients
    recent_logs = DriveLog.query.order_by(
        DriveLog.event_time.desc()
    ).limit(10).all()

    recent_clients = DriveClient.query.order_by(
        DriveClient.last_auth_time.desc()
    ).limit(5).all()

    # Daftar NAS untuk tombol sync
    devices = SynologyDevice.query.filter_by(is_active=True).all()

    # Trend 7 hari
    dates = []
    log_counts = []
    for i in range(6, -1, -1):
        day = datetime.now().date() - timedelta(days=i)
        dates.append(day.strftime('%Y-%m-%d'))
        count = DriveLog.query.filter(
            func.date(DriveLog.event_time) == day
        ).count()
        log_counts.append(count)

    return render_template(
        'dashboard/drive.html',
        total_clients=total_clients,
        online_clients=online_clients,
        offline_clients=offline_clients,
        syncing_clients=syncing_clients,
        total_logs=total_logs,
        logs_today=logs_today,
        recent_logs=recent_logs,
        recent_clients=recent_clients,
        devices=devices,
        dates=dates,
        log_counts=log_counts,
    )


@drive_dashboard_bp.route('/sync/<int:device_id>', methods=['POST'])
@login_required
def sync_now(device_id):
    """Sync Synology Drive untuk device tertentu."""
    if not current_user.is_admin():
        flash('Admin access required.', 'danger')
        return redirect(url_for('drive_dashboard.index'))

    device = SynologyDevice.query.get_or_404(device_id)

    try:
        service = DriveSyncService()
        result = service.sync_device(device, sync_logs=True)

        if result.get('success'):
            flash(
                f"Sync {device.name} OK — "
                f"Clients: +{result.get('clients_created', 0)} new, "
                f"{result.get('clients_updated', 0)} updated | "
                f"Logs: +{result.get('logs_created', 0)} new, "
                f"{result.get('logs_updated', 0)} updated",
                'success'
            )
        else:
            flash(f"Sync {device.name} failed: {result.get('error', 'Unknown error')}", 'danger')
    except Exception as e:
        flash(f"Sync error: {str(e)}", 'danger')

    return redirect(url_for('drive_dashboard.index'))


@drive_dashboard_bp.route('/sync/<int:device_id>/json', methods=['POST'])
@login_required
def sync_now_json(device_id):
    """Sync via AJAX - return JSON."""
    if not current_user.is_admin():
        return jsonify({'success': False, 'message': 'Admin access required'}), 403

    device = SynologyDevice.query.get_or_404(device_id)
    try:
        service = DriveSyncService()
        result = service.sync_device(device, sync_logs=True)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 200