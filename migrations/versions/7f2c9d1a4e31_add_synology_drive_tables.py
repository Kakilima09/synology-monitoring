"""add synology drive clients and logs

Revision ID: 7f2c9d1a4e31
Revises: 1a9742cb926d
"""

from alembic import op
import sqlalchemy as sa


revision = "7f2c9d1a4e31"
down_revision = "1a9742cb926d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "drive_clients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("synology_device_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("device_uuid", sa.String(length=64), nullable=True),
        sa.Column("client_name", sa.String(length=255), nullable=True),
        sa.Column("client_ip", sa.String(length=64), nullable=True),
        sa.Column("client_location", sa.String(length=255), nullable=True),
        sa.Column("client_type", sa.String(length=64), nullable=True),
        sa.Column("client_version", sa.String(length=64), nullable=True),
        sa.Column("client_status", sa.String(length=64), nullable=True),
        sa.Column("client_is_relay", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("client_can_wipe", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_auth_time", sa.BigInteger(), nullable=True),
        sa.Column("login_time", sa.String(length=32), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["synology_device_id"],
            ["synology_devices.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "synology_device_id",
            "client_id",
            name="uq_drive_clients_device_client_id",
        ),
    )
    op.create_index(
        "ix_drive_clients_synology_device_id",
        "drive_clients",
        ["synology_device_id"],
    )
    op.create_index(
        "ix_drive_clients_status",
        "drive_clients",
        ["client_status"],
    )
    op.create_index(
        "ix_drive_clients_last_auth",
        "drive_clients",
        ["last_auth_time"],
    )

    op.create_table(
        "drive_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("synology_device_id", sa.Integer(), nullable=False),
        sa.Column("external_hash", sa.String(length=64), nullable=False),
        sa.Column("event_time", sa.DateTime(), nullable=True),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("client_type", sa.String(length=64), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("activity_type", sa.String(length=64), nullable=True),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column("device_name", sa.String(length=255), nullable=True),
        sa.Column("share_name", sa.String(length=255), nullable=True),
        sa.Column("share_type", sa.String(length=64), nullable=True),
        sa.Column("target", sa.String(length=64), nullable=True),
        sa.Column("target_share_name", sa.String(length=255), nullable=True),
        sa.Column("target_share_type", sa.String(length=64), nullable=True),
        sa.Column("accessable", sa.Boolean(), nullable=True),
        sa.Column("target_accessable", sa.Boolean(), nullable=True),
        sa.Column("p1", sa.Text(), nullable=True),
        sa.Column("p2", sa.Text(), nullable=True),
        sa.Column("raw_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["synology_device_id"],
            ["synology_devices.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "synology_device_id",
            "external_hash",
            name="uq_drive_logs_device_hash",
        ),
    )
    op.create_index(
        "ix_drive_logs_synology_device_id",
        "drive_logs",
        ["synology_device_id"],
    )
    op.create_index(
        "ix_drive_logs_device_time",
        "drive_logs",
        ["synology_device_id", "event_time"],
    )
    op.create_index(
        "ix_drive_logs_username_time",
        "drive_logs",
        ["username", "event_time"],
    )


def downgrade():
    op.drop_index("ix_drive_logs_username_time", table_name="drive_logs")
    op.drop_index("ix_drive_logs_device_time", table_name="drive_logs")
    op.drop_index("ix_drive_logs_synology_device_id", table_name="drive_logs")
    op.drop_table("drive_logs")

    op.drop_index("ix_drive_clients_last_auth", table_name="drive_clients")
    op.drop_index("ix_drive_clients_status", table_name="drive_clients")
    op.drop_index("ix_drive_clients_synology_device_id", table_name="drive_clients")
    op.drop_table("drive_clients")
