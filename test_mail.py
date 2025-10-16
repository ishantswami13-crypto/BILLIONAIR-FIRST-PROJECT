import smtplib
from email.mime.text import MIMEText

SMTP_HOST = "smtp.mailtrap.io"  # or smtp.gmail.com or your provider
SMTP_PORT = 587
SMTP_USERNAME = "YOUR_SMTP_USERNAME"  # replace this
SMTP_PASSWORD = "YOUR_SMTP_PASSWORD"  # replace this
SENDER = "no-reply@yourdomain.com"  # replace this
RECEIVER = "your_real_email@gmail.com"  # replace with your email to receive test mail


def send_test_mail() -> None:
    try:
        msg = MIMEText("This is a test email to confirm SMTP connection. ✅")
        msg["Subject"] = "SMTP Test Successful"
        msg["From"] = SENDER
        msg["To"] = RECEIVER

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            smtp.send_message(msg)

        print("✅ SMTP working — test email sent!")
    except Exception as exc:  # pragma: no cover
        print("❌ SMTP FAILED — error below:")
        print(exc)


if __name__ == "__main__":
    send_test_mail()
