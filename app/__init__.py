import os
import logging
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from config import Config
from .extensions import db, migrate, login_manager, csrf
from .services.backup_sync_service import BackupSyncService

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
    
    # Register blueprints
    from .routes.auth import auth_bp
    from .routes.dashboard import dashboard_bp
    from .routes.synology import synology_bp
    from .routes.backup_jobs import backup_jobs_bp
    from .routes.backup_history import backup_history_bp
    from .routes.alerts import alerts_bp
    from .routes.users import users_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/')
    app.register_blueprint(synology_bp, url_prefix='/synology')
    app.register_blueprint(backup_jobs_bp, url_prefix='/backup-jobs')
    app.register_blueprint(backup_history_bp, url_prefix='/backup-history')
    app.register_blueprint(alerts_bp, url_prefix='/alerts')
    app.register_blueprint(users_bp, url_prefix='/users')

    logging.basicConfig(level=app.config['LOG_LEVEL'])
    app.logger.info('Application started')

    # Register CLI command
    from .commands.sync_backup import sync_backup_command
    app.cli.add_command(sync_backup_command)

    # Scheduler
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        scheduler = BackgroundScheduler()
        sync_interval = app.config['SYNC_INTERVAL_MINUTES']
        scheduler.add_job(
            func=lambda: sync_all_devices(app),
            trigger=IntervalTrigger(minutes=sync_interval),
            id='sync_backup_job',
            replace_existing=True
        )
        scheduler.start()
        app.logger.info(f'Scheduler started with interval {sync_interval} minutes')

    return app

def sync_all_devices(app):
    with app.app_context():
        app.logger.info('Starting scheduled sync')
        try:
            service = BackupSyncService()
            result = service.sync_all_devices()
            app.logger.info(f'Sync completed: {result}')
        except Exception as e:
            app.logger.error(f'Sync failed: {str(e)}')