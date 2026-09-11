from cryptography.fernet import Fernet
from flask import current_app
from ..extensions import db
import base64

class SynologyDevice(db.Model):
    __tablename__ = 'synology_devices'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    host = db.Column(db.String(100), nullable=False)
    port = db.Column(db.Integer, default=5001)
    protocol = db.Column(db.String(10), default='https')
    username = db.Column(db.String(80), nullable=False)
    _password = db.Column('password', db.Text, nullable=True)  # <-- ubah nullable=True untuk sementara
    verify_ssl = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    last_sync_at = db.Column(db.DateTime)
    last_status = db.Column(db.String(20), default='UNKNOWN')
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    backup_jobs = db.relationship('BackupJob', backref='device', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def password(self):
        if not self._password:
            return None
        return self._decrypt(self._password)

    @password.setter
    def password(self, plaintext):
        if plaintext:
            self._password = self._encrypt(plaintext)
        else:
            self._password = None

    def _get_cipher(self):
        # Pastikan SECRET_KEY cukup panjang
        key = current_app.config.get('SECRET_KEY', 'dev-key-change-in-production')
        # Pastikan key length 32 bytes
        if len(key) < 32:
            key = key.ljust(32, '_')
        key_bytes = key[:32].encode('utf-8')
        key_bytes = base64.urlsafe_b64encode(key_bytes.ljust(32, b'_'))
        return Fernet(key_bytes)

    def _encrypt(self, text):
        cipher = self._get_cipher()
        return cipher.encrypt(text.encode()).decode()

    def _decrypt(self, encrypted):
        cipher = self._get_cipher()
        return cipher.decrypt(encrypted.encode()).decode()

    def get_clean_host(self):
        host = self.host
        if host.startswith('http://'):
            host = host[7:]
        elif host.startswith('https://'):
            host = host[8:]
        return host.rstrip('/')

    def get_base_url(self):
        protocol = self.protocol or 'https'
        port = self.port or (443 if protocol == 'https' else 5000)
        return f"{protocol}://{self.get_clean_host()}:{port}"

    def __repr__(self):
        return f'<SynologyDevice {self.name}>'