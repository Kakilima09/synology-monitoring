from flask import Blueprint, render_template, request
from flask_login import login_required
from ..models.drive_log import DriveLog

drive_logs_bp = Blueprint("drive_logs", __name__, url_prefix="/drive/logs")


@drive_logs_bp.route("/")
@login_required
def index():
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


@drive_logs_bp.route("/<int:id>")
@login_required
def show(id):
    log = DriveLog.query.get_or_404(id)
    return render_template("drive/logs/show.html", log=log)