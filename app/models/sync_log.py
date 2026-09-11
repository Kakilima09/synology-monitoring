from ..extensions import db

class SyncLog(db.Model):
    __tablename__ = 'sync_logs'

    id = db.Column(db.Integer, primary_key=True)
    synology_device_id = db.Column(db.Integer, db.ForeignKey('synology_devices.id'), nullable=True)
    started_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    finished_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='RUNNING')
    records_found = db.Column(db.Integer, default=0)
    records_created = db.Column(db.Integer, default=0)
    records_updated = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    device = db.relationship('SynologyDevice', backref='sync_logs')

    def __repr__(self):
        return f'<SyncLog {self.id} {self.status}>'