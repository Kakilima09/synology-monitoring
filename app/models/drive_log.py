from datetime import datetime
from ..extensions import db


class DriveLog(db.Model):
    __tablename__ = "drive_logs"

    id = db.Column(db.Integer, primary_key=True)
    synology_device_id = db.Column(
        db.Integer,
        db.ForeignKey("synology_devices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    external_hash = db.Column(db.String(64), nullable=False)
    event_time = db.Column(db.DateTime, nullable=True, index=True)

    username = db.Column(db.String(255), nullable=True, index=True)
    client_type = db.Column(db.String(64), nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    activity_type = db.Column(db.String(64), nullable=True, index=True)

    source_path = db.Column(db.Text, nullable=True)
    device_name = db.Column(db.String(255), nullable=True)
    share_name = db.Column(db.String(255), nullable=True)
    share_type = db.Column(db.String(64), nullable=True)
    target = db.Column(db.String(64), nullable=True)
    target_share_name = db.Column(db.String(255), nullable=True)
    target_share_type = db.Column(db.String(64), nullable=True)

    accessable = db.Column(db.Boolean, nullable=True)
    target_accessable = db.Column(db.Boolean, nullable=True)

    p1 = db.Column(db.Text, nullable=True)
    p2 = db.Column(db.Text, nullable=True)

    raw_data = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        db.UniqueConstraint(
            "synology_device_id",
            "external_hash",
            name="uq_drive_logs_device_hash",
        ),
        db.Index("ix_drive_logs_device_time", "synology_device_id", "event_time"),
        db.Index("ix_drive_logs_username_time", "username", "event_time"),
    )

    def __repr__(self):
        return f"<DriveLog {self.activity_type} {self.event_time}>"
