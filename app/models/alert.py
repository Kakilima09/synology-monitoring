from ..extensions import db

class Alert(db.Model):
    __tablename__ = 'alerts'

    id = db.Column(db.Integer, primary_key=True)
    backup_history_id = db.Column(db.Integer, db.ForeignKey('backup_histories.id'), nullable=False)
    type = db.Column(db.String(20), default='BACKUP_FAILED')
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    def __repr__(self):
        return f'<Alert {self.id} {self.type}>'