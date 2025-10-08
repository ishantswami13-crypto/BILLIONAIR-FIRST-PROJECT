import sqlite3
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests

DB = "shop.db"

def generate_report():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # Today’s sales only
    today = datetime.date.today().isoformat()

    cur.execute("SELECT COUNT(*), SUM(total) FROM sales WHERE date LIKE ?", (today+"%",))
    sales_data = cur.fetchone()
    total_sales = sales_data[0] or 0
    total_revenue = sales_data[1] or 0

    # Best-selling item
    cur.execute("SELECT item, SUM(quantity) as qty FROM sales WHERE date LIKE ? GROUP BY item ORDER BY qty DESC LIMIT 1", (today+"%",))
    best_item = cur.fetchone()
    best_item = best_item if best_item else ("None", 0)

    # Low-stock items
    cur.execute("SELECT name, current_stock FROM items WHERE current_stock <= 5")
    low_stock = cur.fetchall()

    # Unpaid credits
    cur.execute("SELECT customer_name, item, quantity, total, date FROM credits WHERE status='unpaid'")
    unpaid_credits = cur.fetchall()

    conn.close()

    # Build report
    report = f"""
📅 Daily Report - {today}

🛒 Total Sales: {total_sales}
💰 Total Revenue: ₹{total_revenue}
🏆 Best-Selling Item: {best_item[0]} ({best_item[1]} sold)

⚠️ Low Stock Alerts:
"""
    if low_stock:
        for item in low_stock:
            report += f"- {item[0]} → only {item[1]} left\n"
    else:
        report += "All items in stock ✅\n"

    report += "\n💳 Unpaid Credits (Udhar):\n"
    if unpaid_credits:
        for c in unpaid_credits:
            report += f"- {c[0]} took {c[2]} x {c[1]} (₹{c[3]}) on {c[4]}\n"
    else:
        report += "No unpaid credits ✅\n"

    return report


# ----------------------------
# Send Email
# ----------------------------
def send_email(report):
    sender = "ishantswami13@gmail.com"
    password = "atyfiyssaptwpzuk"   # use App Password if Gmail
    receiver = "ishantchatgpt@gmail.com"

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = receiver
    msg["Subject"] = "Daily Shop Report"
    msg.attach(MIMEText(report, "plain"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())


# ----------------------------
# Send WhatsApp via API (Twilio or UltraMsg)
# ----------------------------
def send_whatsapp(report):
    url = "https://api.ultramsg.com/instanceXXXX/messages/chat"
    token = "YOUR_ULTRAMSG_TOKEN"

    data = {
        "to": "91xxxxxxxxxx",   # your WhatsApp number in international format
        "body": report
    }

    requests.post(url, data=data, headers={"Authorization": f"Bearer {token}"})


# ----------------------------
# Main
# ----------------------------
if __name__ == "__main__":
    report = generate_report()
    print(report)  # preview in terminal
    send_email(report)
    send_whatsapp(report)

def send_daily_report():
    report = generate_report()
    print(report)  # for debugging in terminal
    send_email(report)
    send_whatsapp(report)

if __name__ == "__main__":
    send_daily_report()
