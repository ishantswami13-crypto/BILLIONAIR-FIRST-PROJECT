import sqlite3
from datetime import date
import smtplib

DB = 'shop.db'

def generate_summary():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    today = date.today().isoformat()
    cur.execute("SELECT SUM(total), SUM(quantity) FROM sales WHERE date=?", (today,))
    total_sales, total_items = cur.fetchone()
    
    cur.execute("SELECT name, current_stock FROM items WHERE current_stock < 10")
    low_stock = cur.fetchall()
    conn.close()
    
    summary = f"Daily Sales Summary:\nTotal Items Sold: {total_items}\nTotal Revenue: ₹{total_sales}\n"
    if low_stock:
        summary += "Low Stock Items:\n" + ", ".join([item[0] for item in low_stock])
    else:
        summary += "All items stocked sufficiently."
    return summary

# Example: print summary
print(generate_summary())

# Optional: send email (Gmail)
"""
server = smtplib.SMTP('smtp.gmail.com', 587)
server.starttls()
server.login('your_email@gmail.com', 'your_app_password')
server.sendmail('your_email@gmail.com', 'shop_owner_email@gmail.com', generate_summary())
server.quit()
"""
