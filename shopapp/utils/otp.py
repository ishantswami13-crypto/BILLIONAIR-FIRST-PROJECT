import random
from datetime import datetime, timedelta

from ..extensions import db
from ..models import Otp, User
from .mailer import send_mail

OTP_EXP_MINUTES = 10


def generate_otp(length: int = 6) -> str:
    return ''.join(str(random.randint(0, 9)) for _ in range(length))


def request_otp(username: str, email: str) -> bool:
    code = generate_otp(6)
    now = datetime.utcnow()
    expires = now + timedelta(minutes=OTP_EXP_MINUTES)
    entry = Otp(username=username, email=email, otp=code, created_at=now, expires_at=expires)
    db.session.add(entry)
    db.session.commit()

    send_mail(
        to=email,
        subject='Your ShopApp verification code',
        body=f'Hi {username}, your code is {code}. It expires in {OTP_EXP_MINUTES} minutes.'
    )
    return True


def verify_otp(username: str, email: str, code: str) -> bool:
    now = datetime.utcnow()
    record = (Otp.query
              .filter_by(username=username, email=email, otp=code)
              .order_by(Otp.id.desc())
              .first())
    if record and record.expires_at and record.expires_at > now:
        user = User.query.filter_by(username=username, email=email).first()
        if user:
            user.email_verified = True
        db.session.delete(record)
        db.session.commit()
        return True
    return False
