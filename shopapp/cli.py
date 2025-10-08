import click

from .extensions import db
from .models import ShopProfile, User


def register_cli(app):
    @app.cli.command('seed-admin')
    @click.option('--username', required=True)
    @click.option('--password', required=True)
    @click.option('--email', required=True)
    def seed_admin(username, password, email):
        profile = ShopProfile.query.get(1)
        if not profile:
            db.session.add(ShopProfile(id=1, name='My Shop', address='', phone='', gst=''))

        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)

        db.session.commit()
        click.echo('Admin seeded.')
