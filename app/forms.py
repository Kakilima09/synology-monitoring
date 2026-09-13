from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField, IntegerField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional, NumberRange

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    role = SelectField('Role', choices=[('VIEWER', 'Viewer'), ('ADMIN', 'Admin')], default='VIEWER')
    submit = SubmitField('Register')

class SynologyDeviceForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    host = StringField('Host/IP', validators=[DataRequired()])
    port = IntegerField('Port', validators=[DataRequired(), NumberRange(min=1, max=65535)], default=5001)
    protocol = SelectField('Protocol', choices=[('https', 'HTTPS'), ('http', 'HTTP')], default='https')
    username = StringField('Username', validators=[DataRequired()])
    # Password opsional di form; validasi wajib di-set ulang di route create
    password = PasswordField('Password', validators=[Optional()])
    verify_ssl = BooleanField('Verify SSL', default=False)
    is_active = BooleanField('Active', default=True)
    submit = SubmitField('Save')

class UserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[Optional(), Length(min=6)])
    role = SelectField('Role', choices=[('VIEWER', 'Viewer'), ('ADMIN', 'Admin')], default='VIEWER')
    is_active = BooleanField('Active', default=True)
    submit = SubmitField('Save')

class BackupHistoryFilterForm(FlaskForm):
    synology_device_id = SelectField('Synology', coerce=int, choices=[], validators=[Optional()])
    backup_job_id = SelectField('Backup Job', coerce=int, choices=[], validators=[Optional()])
    status = SelectField(
        'Status',
        choices=[
            ('', 'All'), ('SUCCESS', 'Success'), ('FAILED', 'Failed'),
            ('RUNNING', 'Running'), ('WARNING', 'Warning'), ('UNKNOWN', 'Unknown')
        ],
        validators=[Optional()]
    )
    date_from = StringField('Date From', validators=[Optional()])
    date_to = StringField('Date To', validators=[Optional()])
    submit = SubmitField('Filter')

class DeleteForm(FlaskForm):
    """Form kosong dengan CSRF token untuk aksi delete."""
    submit = SubmitField('Delete')