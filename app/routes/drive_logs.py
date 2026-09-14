from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from ..models.drive_log import DriveLog
from ..services.drive_sync_service import (
    auto_sync_drive_devices,
    sync_all_drive_devices,
)

drive_logs_bp = Blueprint("drive_logs", __name__, url_prefix="/drive/logs")


@drive_logs_bp.route("/")
@login_required
def index():
    auto_sync_drive_devices()

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 25, type=int), 100)
    username = request.args.get("username", "").strip()
    activity_type = request.args.get("type", "").strip()
    search = request.args.get("q", "").strip()

    query = DriveLog.query

    if username:
        query = query.filter(DriveLog.username == username)

    if activity_type:
        query = query.filter(DriveLog.activity_type == activity_type)

    if search:
        like = f"%{search}%"
        query = query.filter(
            DriveLog.source_path.ilike(like)
            | DriveLog.device_name.ilike(like)
            | DriveLog.ip_address.ilike(like)
        )

    pagination = query.order_by(DriveLog.event_time.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return render_template(
        "drive/logs/index.html",
        pagination=pagination,
        logs=pagination.items,
        username=username,
        activity_type=activity_type,
        search=search,
    )


@drive_logs_bp.route("/sync", methods=["POST"])
@login_required
def sync():
    """Sync semua Synology Device aktif (clients + drive logs)."""
    if not current_user.is_admin():
        flash("Admin access required.", "danger")
        return redirect(url_for("drive_logs.index"))

    summary = sync_all_drive_devices(sync_logs=True)

    total = summary.get("total", 0)
    successful = summary.get("successful", 0)

    if summary.get("skipped"):
        flash("Drive sync dilewati: sync sebelumnya masih berjalan.", "warning")
    elif summary.get("success"):
        flash(
            f"Drive sync selesai — {successful}/{total} device sukses.",
            "success",
        )
    else:
        failed = summary.get("results") or []
        detail = "; ".join(
            str(r.get("error", r))
            for r in failed
            if not r.get("success")
        )
        flash(
            f"Drive sync selesai — {successful}/{total} device sukses. "
            f"Gagal: {detail or 'Unknown error'}",
            "danger",
        )

    return redirect(url_for("drive_logs.index"))


@drive_logs_bp.route("/<int:id>")
@login_required
def show(id):
    log = DriveLog.query.get_or_404(id)
    return render_template("drive/logs/show.html", log=log)