import click
from flask.cli import with_appcontext
from ..extensions import db
from ..models import User

@click.command('seed-admin')
@click.option('--username', default='admin', show_default=True, help='Admin username')
@click.option('--email', default=None, help='Admin email (default: <username>@admin.local)')
@click.option('--password', default=None, help='Admin password (default: prompt)')
@click.option('--update', is_flag=True, help='Update credentials jika admin sudah ada')
@with_appcontext
def seed_admin_command(username, email, password, update):
    """Create or update admin user."""
    email = email or f'{username}@admin.local'
    password = password or click.prompt('Admin password', hide_input=True, confirmation_prompt=True)

    user = User.query.filter(User.username == username).first()
    if user:
        if not update:
            click.echo(f'Admin "{username}" sudah ada. Gunakan --update untuk memperbarui kredensial.')
            return
        user.email = email
        user.role = 'ADMIN'
        user.is_active = True
        user.set_password(password)
        db.session.commit()
        click.echo(f'Admin "{username}" diperbarui.')
        return

    user = User(username=username, email=email, role='ADMIN', is_active=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    click.echo(f'Admin "{username}" berhasil dibuat.')