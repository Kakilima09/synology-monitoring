from datetime import datetime
from ..extensions import db


class DriveClient(db.Model):
    __tablename__ = "drive_clients"

    id = db.Column(db.Integer, primary_key=True)
    synology_device_id = db.Column(
        db.Integer,
        db.ForeignKey("synology_devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    client_id = db.Column(db.String(255), nullable=False)
    device_uuid = db.Column(db.String(64), nullable=True)
    client_name = db.Column(db.String(255), nullable=True)
    client_ip = db.Column(db.String(64), nullable=True)
    client_location = db.Column(db.String(255), nullable=True)
    client_type = db.Column(db.String(64), nullable=True)
    client_version = db.Column(db.String(64), nullable=True)
    client_status = db.Column(db.String(64), nullable=True)
    client_is_relay = db.Column(db.Boolean, nullable=False, default=False)
    client_can_wipe = db.Column(db.Boolean, nullable=False, default=False)

    last_auth_time = db.Column(db.BigInteger, nullable=True)
    login_time = db.Column(db.String(32), nullable=True)

    first_seen_at = db.Column(db.DateTime, nullable=True)
    last_seen_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        db.UniqueConstraint(
            "synology_device_id",
            "client_id",
            name="uq_drive_clients_device_client_id",
        ),
        db.Index("ix_drive_clients_status", "client_status"),
        db.Index("ix_drive_clients_last_auth", "last_auth_time"),
    )

    def __repr__(self):
        return f"<DriveClient {self.client_id}>"
