from datetime import datetime

import click

from .extensions import db
from .models import Otp, ShopProfile, User


def register_cli(app):
    @app.cli.command('seed-admin')
    @click.option('--username', required=True)
    @click.option('--password', required=True)
    @click.option('--email', required=True)
    def seed_admin(username, password, email):
        profile = ShopProfile.query.get(1)
        if not profile:
            profile = ShopProfile(
                id=1,
                name='My Shop',
                address='',
                phone='',
                gst='',
                invoice_prefix='INV',
                primary_color='#0A2540',
                secondary_color='#62b5ff',
            )
            db.session.add(profile)

        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)

        db.session.commit()
        click.echo('Admin seeded.')

    @app.cli.command('otp-latest')
    def otp_latest():
        """Print the most recent OTP for manual verification fallback."""
        record = Otp.query.order_by(Otp.id.desc()).first()
        if not record:
            click.echo('No OTP records found.')
            return

        expires = record.expires_at.isoformat() if record.expires_at else 'unknown'
        click.echo(f'Latest OTP: {record.otp}')
        click.echo(f'User: {record.username} <{record.email}>')
        click.echo(f'Expires at: {expires}')
        if record.expires_at:
            remaining = (record.expires_at - datetime.utcnow()).total_seconds() / 60
            if remaining > 0:
                click.echo(f'Remaining: ~{remaining:.0f} minute(s)')
            else:
                click.echo('Status: expired')
