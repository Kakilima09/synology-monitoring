from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required
from ..extensions import db
from ..models import Alert

alerts_bp = Blueprint('alerts', __name__)

@alerts_bp.route('/')
@login_required
def index():
    alerts = Alert.query.order_by(Alert.created_at.desc()).paginate(page=request.args.get('page', 1, type=int), per_page=20)
    return render_template('alerts/index.html', alerts=alerts)

@alerts_bp.route('/<int:id>/mark-read', methods=['POST'])
@login_required
def mark_read(id):
    alert = Alert.query.get_or_404(id)
    alert.is_read = True
    db.session.commit()
    return jsonify({'success': True})

@alerts_bp.route('/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    Alert.query.filter_by(is_read=False).update({'is_read': True})
    db.session.commit()
    flash('All alerts marked as read.', 'success')
    return redirect(url_for('alerts.index'))