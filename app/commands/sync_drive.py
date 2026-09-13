import click
from flask.cli import with_appcontext

from ..services.drive_sync_service import sync_all_drive_devices


@click.command("sync-drive")
@click.option(
    "--no-logs",
    is_flag=True,
    default=False,
    help="Only synchronize clients, skip Drive logs.",
)
@with_appcontext
def sync_drive_command(no_logs=False):
    """Synchronize Synology Drive clients and logs."""
    summary = sync_all_drive_devices(sync_logs=not no_logs)

    if summary.get("skipped"):
        click.echo("Skipped: another sync is still running.")
        return

    results = summary.get("results", [])

    ok = 0
    for result in results:
        if result.get("success"):
            ok += 1
            click.echo(
                "OK: clients +%s/~%s, logs +%s/~%s"
                % (
                    result.get("clients_created", 0),
                    result.get("clients_updated", 0),
                    result.get("logs_created", 0),
                    result.get("logs_updated", 0),
                )
            )
        else:
            click.echo("ERROR: %s" % result.get("error", result))

    click.echo(f"Synced {ok}/{len(results)} device(s).")
