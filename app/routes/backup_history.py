# app/routes/backup_history.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from sqlalchemy import and_
from ..extensions import db
from ..models import BackupHistory, BackupJob, SynologyDevice
from ..forms import BackupHistoryFilterForm
from datetime import datetime

backup_history_bp = Blueprint('backup_history', __name__)

@backup_history_bp.route('/')
@login_required
def index():
    form = BackupHistoryFilterForm()
    # Populate choices
    form.synology_device_id.choices = [(0, 'All')] + [(d.id, d.name) for d in SynologyDevice.query.all()]
    form.backup_job_id.choices = [(0, 'All')] + [(j.id, j.job_name) for j in BackupJob.query.all()]

    query = BackupHistory.query
    # Apply filters
    if request.args.get('synology_device_id') and request.args.get('synology_device_id') != '0':
        query = query.filter_by(synology_device_id=int(request.args.get('synology_device_id')))
    if request.args.get('backup_job_id') and request.args.get('backup_job_id') != '0':
        query = query.filter_by(backup_job_id=int(request.args.get('backup_job_id')))
    if request.args.get('status'):
        query = query.filter_by(status=request.args.get('status'))
    if request.args.get('date_from'):
        try:
            date_from = datetime.strptime(request.args.get('date_from'), '%Y-%m-%d')
            query = query.filter(BackupHistory.started_at >= date_from)
        except:
            pass
    if request.args.get('date_to'):
        try:
            date_to = datetime.strptime(request.args.get('date_to'), '%Y-%m-%d')
            query = query.filter(BackupHistory.started_at <= date_to)
        except:
            pass

    histories = query.order_by(BackupHistory.started_at.desc()).paginate(
        page=request.args.get('page', 1, type=int), per_page=20
    )
    return render_template('backup_history/index.html', histories=histories, form=form)

@backup_history_bp.route('/<int:id>')
@login_required
def detail(id):
    history = BackupHistory.query.get_or_404(id)
    return render_template('backup_history/detail.html', history=history)