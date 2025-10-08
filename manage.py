from flask_migrate import Migrate

from shopapp import create_app
from shopapp.extensions import db
from shopapp.models import *  # noqa

app = create_app()
Migrate(app, db)


if __name__ == '__main__':
    app.run()
