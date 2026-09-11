from ..extensions import db

class BackupHistory(db.Model):
    __tablename__ = 'backup_histories'

    id = db.Column(db.Integer, primary_key=True)
    synology_device_id = db.Column(db.Integer, db.ForeignKey('synology_devices.id'), nullable=False)
    backup_job_id = db.Column(db.Integer, db.ForeignKey('backup_jobs.id'), nullable=False)
    external_backup_id = db.Column(db.String(100))
    started_at = db.Column(db.DateTime, nullable=False)
    finished_at = db.Column(db.DateTime)
    duration_seconds = db.Column(db.Float)
    status = db.Column(db.String(20), default='UNKNOWN')
    backup_size = db.Column(db.BigInteger)
    file_count = db.Column(db.Integer)
    source = db.Column(db.String(200))
    destination = db.Column(db.String(200))
    error_message = db.Column(db.Text)
    raw_status = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    # Unique constraint to prevent duplicates (assuming external_backup_id + device is unique)
    __table_args__ = (
        db.UniqueConstraint('synology_device_id', 'external_backup_id', name='uq_device_external_backup'),
    )

    device = db.relationship('SynologyDevice', backref='histories')
    alerts = db.relationship('Alert', backref='backup_history', lazy='dynamic')

    def __repr__(self):
        return f'<BackupHistory {self.id} {self.status}>'