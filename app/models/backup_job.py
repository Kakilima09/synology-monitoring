from ..extensions import db

class BackupJob(db.Model):
    __tablename__ = 'backup_jobs'

    id = db.Column(db.Integer, primary_key=True)
    synology_device_id = db.Column(db.Integer, db.ForeignKey('synology_devices.id'), nullable=False)
    external_job_id = db.Column(db.String(100))
    job_name = db.Column(db.String(200), nullable=False)
    backup_type = db.Column(db.String(50))
    source = db.Column(db.String(200))
    destination = db.Column(db.String(200))
    schedule = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    last_status = db.Column(db.String(20), default='UNKNOWN')
    last_run_at = db.Column(db.DateTime)
    next_run_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    histories = db.relationship('BackupHistory', backref='job', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<BackupJob {self.job_name}>'