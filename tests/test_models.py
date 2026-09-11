import pytest
from datetime import datetime
from app.models import User, SynologyDevice, BackupJob, BackupHistory, SyncLog, Alert
from app.extensions import db

def test_user_creation(app):
    with app.app_context():
        user = User(username='testuser', email='test@example.com', role='VIEWER')
        user.set_password('password')
        db.session.add(user)
        db.session.commit()
        assert user.id is not None
        assert user.check_password('password') is True

def test_synology_device_encryption(app):
    with app.app_context():
        device = SynologyDevice(name='test', host='192.168.1.1', port=5000, protocol='http',
                                username='admin', password='secret', verify_ssl=False)
        db.session.add(device)
        db.session.commit()
        # Check that password is encrypted in DB
        assert device._password != 'secret'
        # Check decryption works
        assert device.password == 'secret'

def test_backup_history_unique_constraint(app):
    with app.app_context():
        device = SynologyDevice(name='test', host='192.168.1.1', port=5000, protocol='http',
                                username='admin', password='secret')
        db.session.add(device)
        db.session.commit()
        job = BackupJob(synology_device_id=device.id, job_name='Test Job', external_job_id='JOB1')
        db.session.add(job)
        db.session.commit()
        history1 = BackupHistory(
            synology_device_id=device.id,
            backup_job_id=job.id,
            external_backup_id='BACKUP1',
            started_at=datetime.now(),
            status='SUCCESS'
        )
        db.session.add(history1)
        db.session.commit()
        # Try to add duplicate external_backup_id
        history2 = BackupHistory(
            synology_device_id=device.id,
            backup_job_id=job.id,
            external_backup_id='BACKUP1',
            started_at=datetime.now(),
            status='FAILED'
        )
        db.session.add(history2)
        with pytest.raises(Exception):  # IntegrityError
            db.session.commit()