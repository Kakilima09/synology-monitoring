import csv
import io
from datetime import datetime
from flask import Blueprint, render_template, request, Response
from flask_login import login_required
from ..models import BackupHistory, DriveLog

export_logs_bp = Blueprint("export_logs", __name__, url_prefix="/export")


@export_logs_bp.route("/")
@login_required
def index():
    return render_template("export/index.html")


@export_logs_bp.route("/download")
@login_required
def download():
    log_type = request.args.get("type", "backup")
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    output = io.StringIO()
    writer = csv.writer(output)

    if log_type == "drive":
        filename = "log-drive"
        writer.writerow(
            [
                "event_time",
                "username",
                "activity_type",
                "device_name",
                "ip_address",
                "source_path",
                "target",
                "target_share_name",
            ]
        )
        query = DriveLog.query
        if date_from:
            try:
                query = query.filter(
                    DriveLog.event_time >= datetime.strptime(
                        date_from, "%Y-%m-%d"
                    )
                )
            except ValueError:
                pass
        if date_to:
            try:
                query = query.filter(
                    DriveLog.event_time
                    <= datetime.strptime(date_to, "%Y-%m-%d").replace(
                        hour=23, minute=59, second=59
                    )
                )
            except ValueError:
                pass
        for log in query.order_by(DriveLog.event_time.desc()).yield_per(1000):
            writer.writerow(
                [
                    log.event_time.isoformat() if log.event_time else "",
                    log.username or "",
                    log.activity_type or "",
                    log.device_name or "",
                    log.ip_address or "",
                    log.source_path or "",
                    log.target or "",
                    log.target_share_name or "",
                ]
            )
    else:
        filename = "log-backup"
        writer.writerow(
            [
                "device",
                "job",
                "status",
                "started_at",
                "finished_at",
                "backup_size",
                "file_count",
                "error_message",
            ]
        )
        query = BackupHistory.query
        if date_from:
            try:
                query = query.filter(
                    BackupHistory.started_at >= datetime.strptime(
                        date_from, "%Y-%m-%d"
                    )
                )
            except ValueError:
                pass
        if date_to:
            try:
                query = query.filter(
                    BackupHistory.started_at
                    <= datetime.strptime(date_to, "%Y-%m-%d").replace(
                        hour=23, minute=59, second=59
                    )
                )
            except ValueError:
                pass
        for history in query.order_by(BackupHistory.started_at.desc()):
            writer.writerow(
                [
                    history.device.name if history.device else "",
                    history.job.job_name if history.job else "",
                    history.status or "",
                    history.started_at.isoformat() if history.started_at else "",
                    history.finished_at.isoformat() if history.finished_at else "",
                    history.backup_size if history.backup_size is not None else "",
                    history.file_count if history.file_count is not None else "",
                    history.error_message or "",
                ]
            )

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename}-'
                f'{datetime.now().strftime("%Y%m%d-%H%M")}.csv"'
            )
        },
    )