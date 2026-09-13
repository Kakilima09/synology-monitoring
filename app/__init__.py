import os
import logging
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from config import Config
from .extensions import db, migrate, login_manager, csrf


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # ====== USER LOADER ======
    @login_manager.user_loader
    def load_user(user_id):
        from .models import User
        return User.query.get(int(user_id))

    @app.context_processor
    def inject_csrf_token():
        from flask_wtf.csrf import generate_csrf
        return dict(csrf_token=generate_csrf)

    # ====== BLUEPRINTS ======
    from .routes.auth import auth_bp
    from .routes.dashboard import dashboard_bp
    from .routes.synology import synology_bp
    from .routes.backup_jobs import backup_jobs_bp
    from .routes.backup_history import backup_history_bp
    from .routes.alerts import alerts_bp
    from .routes.users import users_bp
    from .routes.drive_clients import drive_clients_bp
    from .routes.drive_logs import drive_logs_bp
    from .routes.drive_dashboard import drive_dashboard_bp
    from .routes.export_logs import export_logs_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/')
    app.register_blueprint(synology_bp, url_prefix='/synology')
    app.register_blueprint(backup_jobs_bp, url_prefix='/backup-jobs')
    app.register_blueprint(backup_history_bp, url_prefix='/backup-history')
    app.register_blueprint(alerts_bp, url_prefix='/alerts')
    app.register_blueprint(users_bp, url_prefix='/users')
    app.register_blueprint(drive_clients_bp)
    app.register_blueprint(drive_logs_bp)
    app.register_blueprint(drive_dashboard_bp)
    app.register_blueprint(export_logs_bp)

    logging.basicConfig(level=app.config['LOG_LEVEL'])
    app.logger.info('Application started')

    # ====== CLI COMMANDS ======
    from .commands.sync_backup import sync_backup_command
    from .commands.sync_drive import sync_drive_command
    app.cli.add_command(sync_backup_command)
    app.cli.add_command(sync_drive_command)

    # ====== SCHEDULER ======
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        scheduler = BackgroundScheduler()
        sync_interval = app.config['SYNC_INTERVAL_MINUTES']
        scheduler.add_job(
            func=lambda: sync_all_drive(app),
            trigger=IntervalTrigger(minutes=sync_interval),
            id='sync_drive_job',
            replace_existing=True
        )
        scheduler.start()
        app.logger.info(f'Drive scheduler started every {sync_interval} minutes')

    return app


def sync_all_drive(app):
    """Sync Synology Drive clients & logs untuk semua NAS aktif."""
    with app.app_context():
        app.logger.info('Starting scheduled Synology Drive sync')
        try:
            from .models import SynologyDevice
            from .services.drive_sync_service import DriveSyncService

            service = DriveSyncService()
            devices = SynologyDevice.query.filter_by(is_active=True).all()

            for device in devices:
                try:
                    result = service.sync_device(device, sync_logs=True)
                    app.logger.info(f"Drive sync {device.name}: {result}")
                except Exception as e:
                    app.logger.error(f"Drive sync {device.name} failed: {e}")
        except Exception as e:
            app.logger.exception(f'Scheduled Drive sync failed: {e}')