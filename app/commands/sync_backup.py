import click
from flask.cli import with_appcontext
from ..services.backup_sync_service import BackupSyncService

@click.command('sync-backup')
@click.option('--device-id', type=int, help='Sync a specific device by ID')
@click.option('--mock', is_flag=True, help='Use mock service (default: False)')
@with_appcontext
def sync_backup_command(device_id, mock):
    """Manually trigger backup synchronization (real API by default)."""
    service = BackupSyncService(use_mock=mock)
    if device_id:
        from ..models import SynologyDevice
        device = SynologyDevice.query.get(device_id)
        if not device:
            click.echo(f"Device with ID {device_id} not found.")
            return
        result = service.sync_device(device)
        click.echo(f"Sync result: {result}")
    else:
        results = service.sync_all_devices()
        for res in results:
            click.echo(f"Sync result: {res}")