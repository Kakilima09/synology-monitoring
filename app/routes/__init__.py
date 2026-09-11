# This file makes the routes directory a Python package.
# It can be empty, or you can import blueprints here for convenience.

from .auth import auth_bp
from .dashboard import dashboard_bp
from .synology import synology_bp
from .backup_jobs import backup_jobs_bp
from .backup_history import backup_history_bp
from .alerts import alerts_bp
from .users import users_bp

# You can also define a list of all blueprints for registration in the factory.
__all__ = [
    'auth_bp', 'dashboard_bp', 'synology_bp', 'backup_jobs_bp',
    'backup_history_bp', 'alerts_bp', 'users_bp'
]