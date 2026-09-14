from flask import Blueprint, render_template, request, abort
from flask_login import login_required
from ..models.drive_client import DriveClient
from ..services.drive_sync_service import auto_sync_drive_devices

drive_clients_bp = Blueprint("drive_clients", __name__, url_prefix="/drive/clients")


@drive_clients_bp.route("/")
@login_required
def index():
    auto_sync_drive_devices()

    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 25, type=int), 100)
    status = request.args.get("status", "").strip()
    search = request.args.get("q", "").strip()

    query = DriveClient.query

    if status:
        query = query.filter(DriveClient.client_status == status)

    if search:
        like = f"%{search}%"
        query = query.filter(
            DriveClient.client_id.ilike(like)
            | DriveClient.client_name.ilike(like)
            | DriveClient.client_ip.ilike(like)
        )

    pagination = query.order_by(
        DriveClient.last_auth_time.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    return render_template(
        "drive/clients/index.html",
        pagination=pagination,
        clients=pagination.items,
        status=status,
        search=search,
    )


@drive_clients_bp.route("/<int:id>")
@login_required
def show(id):
    client = DriveClient.query.get_or_404(id)
    return render_template("drive/clients/show.html", client=client)