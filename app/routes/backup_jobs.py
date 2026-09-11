from flask import Blueprint, render_template
from flask_login import login_required
from ..models import BackupJob

backup_jobs_bp = Blueprint('backup_jobs', __name__)

@backup_jobs_bp.route('/')
@login_required
def index():
    jobs = BackupJob.query.order_by(BackupJob.job_name).all()
    return render_template('backup_jobs/index.html', jobs=jobs)