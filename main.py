import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# ========== CONFIG ========== #
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
TO_EMAIL = GMAIL_ADDRESS  # You can customize this if needed
MENTION_THRESHOLD = 300
APE_URL = 'https://apewisdom.io/api/v1.0/filter/all-stocks/page/1'
# ============================ #

def fetch_mentions():
    try:
        resp = requests.get(APE_URL)
        return resp.json().get('results', [])
    except Exception as e:
        print(f"❌ Failed to fetch ApeWisdom data: {e}")
        return []

def build_alert_email(spikes):
    if not spikes:
        return "<p>No significant WSB mention spikes today.</p>"

    buy_lines = ""
    sell_lines = ""
    summary_lines = ""

    for s in spikes:
        ticker = s.get('ticker', '???')
        mentions = s.get('mentions', 0)

        if mentions >= 800:
            sell_lines += f"⚠️ <b>Sell Signal:</b> {ticker} mentions spiked to {mentions}<br>"
        elif mentions >= MENTION_THRESHOLD:
            buy_lines += f"🚀 <b>Buy Signal:</b> {ticker} mentions up to {mentions}<br>"

        summary_lines += f"📊 {ticker}: {mentions} mentions<br>"

    html = ""
    if buy_lines:
        html += f"<h3>🚀 Buy Alerts</h3>{buy_lines}<br>"
    if sell_lines:
        html += f"<h3>⚠️ Sell Alerts</h3>{sell_lines}<br>"
    html += f"<h3>📊 Daily Summary (8 AM PT)</h3>{summary_lines}"
    html += "<p style='font-size:12px;color:gray;'>Auto-generated from your meme stock alert system.</p>"
    return html

def send_email(subject, html_body):
    msg = MIMEMultipart("alternative")
    msg['From'] = GMAIL_ADDRESS
    msg['To'] = TO_EMAIL
    msg['Subject'] = subject
    msg.attach(MIMEText(html_body, 'html'))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, TO_EMAIL, msg.as_string())
        print("✅ Email sent successfully.")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

def run_alert():
    data = fetch_mentions()
    spikes = [t for t in data if t.get('mentions', 0) >= MENTION_THRESHOLD]
    if spikes:
        html = build_alert_email(spikes)
        send_email("🚨 WSB Buy/Sell Signal Report", html)
    else:
        print("ℹ️ No mentions exceeded threshold.")

if __name__ == "__main__":
    run_alert()
