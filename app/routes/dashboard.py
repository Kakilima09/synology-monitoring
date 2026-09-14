from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func
from datetime import datetime, timedelta
from ..models import SynologyDevice, BackupJob, BackupHistory, Alert, DriveClient, DriveLog, SyncLog
from ..extensions import db

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def index():
    # ===== Devices =====
    devices = SynologyDevice.query.order_by(SynologyDevice.id).all()
    total_devices = len(devices)
    online_devices = SynologyDevice.query.filter_by(last_status='ONLINE').count()
    offline_devices = SynologyDevice.query.filter_by(last_status='ERROR').count()
    unknown_devices = total_devices - online_devices - offline_devices

    # ===== Backup =====
    total_jobs = BackupJob.query.count()

    today = func.date(func.now())
    backup_today = BackupHistory.query.filter(
        func.date(BackupHistory.started_at) == today
    ).count()
    failed_today = BackupHistory.query.filter(
        func.date(BackupHistory.started_at) == today,
        BackupHistory.status == 'FAILED'
    ).count()

    success_count = BackupHistory.query.filter_by(status='SUCCESS').count()
    failed_count = BackupHistory.query.filter_by(status='FAILED').count()
    running_count = BackupHistory.query.filter_by(status='RUNNING').count()
    warning_count = BackupHistory.query.filter_by(status='WARNING').count()

    recent_histories = BackupHistory.query.order_by(
        BackupHistory.started_at.desc()
    ).limit(10).all()

    # ===== Drive clients & logs =====
    total_clients = DriveClient.query.count()
    online_clients = DriveClient.query.filter_by(client_status='on_line').count()
    offline_clients = DriveClient.query.filter_by(client_status='off_line').count()
    syncing_clients = DriveClient.query.filter_by(client_status='syncing').count()

    total_logs = DriveLog.query.count()
    logs_today = DriveLog.query.filter(
        func.date(DriveLog.event_time) == today
    ).count()

    recent_logs = DriveLog.query.order_by(
        DriveLog.event_time.desc()
    ).limit(10).all()

    recent_clients = DriveClient.query.order_by(
        DriveClient.last_auth_time.desc()
    ).limit(5).all()

    # ===== Alerts =====
    unread_alerts = Alert.query.filter_by(is_read=False).count()
    recent_alerts = Alert.query.order_by(Alert.created_at.desc()).limit(5).all()

    # ===== Sync logs (aktivitas sync terakhir) =====
    recent_syncs = SyncLog.query.order_by(SyncLog.id.desc()).limit(8).all()

    # ===== Data grafik backup 7 hari terakhir =====
    dates = []
    success_counts = []
    failed_counts = []
    for i in range(6, -1, -1):
        day = datetime.now().date() - timedelta(days=i)
        dates.append(day.strftime('%Y-%m-%d'))
        success_counts.append(BackupHistory.query.filter(
            func.date(BackupHistory.started_at) == day,
            BackupHistory.status == 'SUCCESS'
        ).count())
        failed_counts.append(BackupHistory.query.filter(
            func.date(BackupHistory.started_at) == day,
            BackupHistory.status == 'FAILED'
        ).count())

    # ===== Data grafik aktivitas Drive 7 hari terakhir =====
    drive_dates = []
    drive_log_counts = []
    for i in range(6, -1, -1):
        day = datetime.now().date() - timedelta(days=i)
        drive_dates.append(day.strftime('%Y-%m-%d'))
        drive_log_counts.append(DriveLog.query.filter(
            func.date(DriveLog.event_time) == day
        ).count())

    # ===== Sembunyikan section backup bila tidak ada datanya =====
    has_backup_data = bool(
        total_jobs > 0
        or backup_today > 0
        or success_count > 0
        or failed_count > 0
        or running_count > 0
        or warning_count > 0
        or recent_histories
    )

    return render_template(
        'dashboard/index.html',
        devices=devices,
        total_devices=total_devices,
        online_devices=online_devices,
        offline_devices=offline_devices,
        unknown_devices=unknown_devices,
        total_jobs=total_jobs,
        backup_today=backup_today,
        failed_today=failed_today,
        success_count=success_count,
        failed_count=failed_count,
        running_count=running_count,
        warning_count=warning_count,
        recent_histories=recent_histories,
        unread_alerts=unread_alerts,
        recent_alerts=recent_alerts,
        total_clients=total_clients,
        online_clients=online_clients,
        offline_clients=offline_clients,
        syncing_clients=syncing_clients,
        total_logs=total_logs,
        logs_today=logs_today,
        recent_logs=recent_logs,
        recent_clients=recent_clients,
        recent_syncs=recent_syncs,
        dates=dates,
        success_counts=success_counts,
        failed_counts=failed_counts,
        drive_dates=drive_dates,
        drive_log_counts=drive_log_counts,
        has_backup_data=has_backup_data,
    )