from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func
from datetime import datetime, timedelta
from ..models import SynologyDevice, BackupJob, BackupHistory, Alert
from ..extensions import db

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def index():
    total_devices = SynologyDevice.query.count()
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

    unread_alerts = Alert.query.filter_by(is_read=False).count()

    # Data untuk grafik 7 hari terakhir
    dates = []
    success_counts = []
    failed_counts = []
    for i in range(6, -1, -1):
        day = datetime.now().date() - timedelta(days=i)
        dates.append(day.strftime('%Y-%m-%d'))
        success = BackupHistory.query.filter(
            func.date(BackupHistory.started_at) == day,
            BackupHistory.status == 'SUCCESS'
        ).count()
        failed = BackupHistory.query.filter(
            func.date(BackupHistory.started_at) == day,
            BackupHistory.status == 'FAILED'
        ).count()
        success_counts.append(success)
        failed_counts.append(failed)

    return render_template(
        'dashboard/index.html',
        total_devices=total_devices,
        total_jobs=total_jobs,
        backup_today=backup_today,
        failed_today=failed_today,
        success_count=success_count,
        failed_count=failed_count,
        running_count=running_count,
        warning_count=warning_count,
        recent_histories=recent_histories,
        unread_alerts=unread_alerts,
        dates=dates,
        success_counts=success_counts,
        failed_counts=failed_counts
    )