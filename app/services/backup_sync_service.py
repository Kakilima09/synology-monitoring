import logging
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from ..extensions import db
from ..models import SynologyDevice, BackupJob, BackupHistory, SyncLog
from .synology_service import SynologyService, MockSynologyService
from .notification_service import NotificationService

logger = logging.getLogger(__name__)

class BackupSyncService:
    def __init__(self, use_mock=False):
        self.use_mock = use_mock
        self.notification = NotificationService()

    def sync_all_devices(self):
        devices = SynologyDevice.query.filter_by(is_active=True).all()
        results = []
        for device in devices:
            result = self.sync_device(device)
            results.append(result)
        return results

    def sync_device(self, device):
        log_entry = SyncLog(
            synology_device_id=device.id,
            started_at=datetime.now(),
            status='RUNNING'
        )
        db.session.add(log_entry)
        db.session.commit()

        try:
            # Pilih service (mock atau real)
            if self.use_mock:
                service = MockSynologyService(device)
            else:
                service = SynologyService(device)

            # Test connection (termasuk discovery & login)
            conn_test = service.test_connection()
            if not conn_test['success']:
                raise Exception(f"Connection failed: {conn_test['message']}")

            # Update device status
            device.last_status = 'ONLINE'
            device.last_sync_at = datetime.now()
            # Simpan client info jika ada
            if 'client_info' in conn_test:
                client_info = conn_test['client_info']
                # opsional: simpan ke device jika ada kolom tambahan
                # device.model = client_info.get('model')
                # device.firmware = client_info.get('firmware')
            db.session.commit()

            # Ambil tasks
            tasks = service.get_backup_tasks()
            records_found = len(tasks)
            records_created = 0
            records_updated = 0

            for task_data in tasks:
                # Cari job berdasarkan external_job_id
                job = BackupJob.query.filter_by(
                    synology_device_id=device.id,
                    external_job_id=str(task_data.get('id'))
                ).first()

                if not job:
                    job = BackupJob(
                        synology_device_id=device.id,
                        external_job_id=str(task_data.get('id')),
                        job_name=task_data.get('name', 'Unknown'),
                        backup_type=task_data.get('type', 'Unknown'),
                        source=task_data.get('source'),
                        destination=task_data.get('destination'),
                        schedule=task_data.get('schedule'),
                        is_active=True
                    )
                    db.session.add(job)
                    records_created += 1
                else:
                    # Update jika ada perubahan
                    job.job_name = task_data.get('name', job.job_name)
                    job.backup_type = task_data.get('type', job.backup_type)
                    job.source = task_data.get('source', job.source)
                    job.destination = task_data.get('destination', job.destination)
                    job.schedule = task_data.get('schedule', job.schedule)
                    records_updated += 1

                # Ambil history untuk task ini
                histories = service.get_backup_history(task_data.get('id'), limit=50)
                for hist in histories:
                    # Cek duplikat berdasarkan external_backup_id
                    existing = BackupHistory.query.filter_by(
                        synology_device_id=device.id,
                        external_backup_id=str(hist.get('external_id'))
                    ).first()

                    if existing:
                        # Update jika ada perubahan status atau lainnya
                        existing.status = hist.get('status', existing.status).upper()
                        existing.finished_at = self._parse_datetime(hist.get('finished_at'))
                        existing.duration_seconds = hist.get('duration_seconds')
                        existing.backup_size = hist.get('backup_size')
                        existing.file_count = hist.get('file_count')
                        existing.error_message = hist.get('error_message')
                        records_updated += 1
                    else:
                        new_history = BackupHistory(
                            synology_device_id=device.id,
                            backup_job_id=job.id,
                            external_backup_id=str(hist.get('external_id')),
                            started_at=self._parse_datetime(hist.get('started_at')),
                            finished_at=self._parse_datetime(hist.get('finished_at')),
                            duration_seconds=hist.get('duration_seconds'),
                            status=hist.get('status', 'UNKNOWN').upper(),
                            backup_size=hist.get('backup_size'),
                            file_count=hist.get('file_count'),
                            source=hist.get('source'),
                            destination=hist.get('destination'),
                            error_message=hist.get('error_message'),
                            raw_status=hist.get('raw_status')
                        )
                        db.session.add(new_history)
                        records_created += 1

                        # Buat alert jika status FAILED
                        if new_history.status == 'FAILED':
                            self._create_alert(new_history)

            # Update log
            log_entry.status = 'SUCCESS'
            log_entry.records_found = records_found
            log_entry.records_created = records_created
            log_entry.records_updated = records_updated
            log_entry.finished_at = datetime.now()
            db.session.commit()

            logger.info(f"Sync {device.name}: found {records_found}, created {records_created}, updated {records_updated}")
            return {
                'device': device.name,
                'status': 'SUCCESS',
                'records_found': records_found,
                'records_created': records_created,
                'records_updated': records_updated
            }

        except Exception as e:
            logger.error(f"Sync failed for {device.name}: {str(e)}")
            device.last_status = 'ERROR'
            db.session.commit()

            log_entry.status = 'FAILED'
            log_entry.error_message = str(e)
            log_entry.finished_at = datetime.now()
            db.session.commit()

            return {
                'device': device.name,
                'status': 'FAILED',
                'error': str(e)
            }

    def _parse_datetime(self, dt_str):
        if dt_str is None:
            return None
        try:
            # Coba parsing ISO format
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except:
            return None

    def _create_alert(self, history):
        from ..models import Alert
        alert = Alert(
            backup_history_id=history.id,
            type='BACKUP_FAILED',
            title=f"Backup failed: {history.job.job_name}",
            message=history.error_message or "No error details provided.",
            is_read=False
        )
        db.session.add(alert)
        self.notification.send_alert(alert)