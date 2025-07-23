import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import csv
from datetime import datetime, timedelta
from collections import defaultdict

# ========== CONFIG ========== #
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
TO_EMAIL = "(GMAIL_ADDRESS")

MENTION_THRESHOLD = 300        # Minimum mentions for Buy signal
SELL_MULTIPLIER = 2.0          # Sell if ≥ 2x 7-day average and ≥ 800 mentions
BUY_MULTIPLIER = 1.3           # Buy if ≥ 1.3x 7-day average
HISTORY_FILE = "history.csv"
APE_URL = "https://apewisdom.io/api/v1.0/filter/all-stocks/page/1"
# ============================ #

def fetch_mentions():
    """Fetch real-time mentions from ApeWisdom API."""
    try:
        resp = requests.get(APE_URL)
        return resp.json().get('results', [])
    except Exception as e:
        print(f"❌ Failed to fetch ApeWisdom data: {e}")
        return []

def load_history():
    """Load historical mention data from CSV."""
    history = defaultdict(list)
    if not os.path.exists(HISTORY_FILE):
        return history

    with open(HISTORY_FILE, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            history[row["ticker"]].append({
                "date": datetime.strptime(row["date"], "%Y-%m-%d"),
                "mentions": int(row["mentions"])
            })
    return history

def save_today_mentions(data):
    """Append today's mentions to history.csv."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    file_exists = os.path.exists(HISTORY_FILE)

    with open(HISTORY_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "ticker", "mentions"])
        if not file_exists:
            writer.writeheader()
        for t in data:
            writer.writerow({
                "date": today,
                "ticker": t.get("ticker"),
                "mentions": t.get("mentions", 0)
            })

def compute_7day_average(history, ticker):
    """Compute 7-day average mentions for a ticker."""
    today = datetime.utcnow()
    past_week = today - timedelta(days=7)

    mentions = [
        h["mentions"]
        for h in history.get(ticker, [])
        if h["date"] >= past_week
    ]

    return sum(mentions) / len(mentions) if mentions else 0

def build_alert_email(spikes, history):
    """Build HTML email using 7-day average comparison, showing ratio."""
    if not spikes:
        return "<p>No significant WSB mention spikes today.</p>"

    buy_lines = ""
    sell_lines = ""
    summary_lines = ""

    for s in spikes:
        ticker = s.get("ticker", "???")
        mentions = s.get("mentions", 0)
        avg_7d = compute_7day_average(history, ticker)
        ratio = mentions / avg_7d if avg_7d else 0

        # Format ratio nicely (e.g., 2.3x avg)
        ratio_text = f"{ratio:.1f}× avg"

        if mentions >= 800 and ratio >= SELL_MULTIPLIER:
            sell_lines += f"⚠️ <b>Sell Signal:</b> {ticker} — {mentions} vs {avg_7d:.0f} ({ratio_text})<br>"
        elif mentions >= MENTION_THRESHOLD and ratio >= BUY_MULTIPLIER:
            buy_lines += f"🚀 <b>Buy Signal:</b> {ticker} — {mentions} vs {avg_7d:.0f} ({ratio_text})<br>"

        summary_lines += f"📊 {ticker}: {mentions} mentions (7d avg: {avg_7d:.0f})<br>"

    html = ""
    if buy_lines:
        html += f"<h3>🚀 Buy Alerts</h3>{buy_lines}<br>"
    if sell_lines:
        html += f"<h3>⚠️ Sell Alerts</h3>{sell_lines}<br>"
    html += f"<h3>📊 Daily Summary (8 AM PT)</h3>{summary_lines}"
    html += "<p style='font-size:12px;color:gray;'>Auto-generated from your meme stock alert system (7-day average logic).</p>"
    return html

def send_email(subject, html_body):
    """Send email via Gmail SMTP."""
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
    """Main function to fetch, save, compute averages, and send alert."""
    data = fetch_mentions()
    if not data:
        print("No data from API — aborting run.")
        return

    # Save today's mentions
    save_today_mentions(data)

    # Load full history and compute signals
    history = load_history()
    spikes = [t for t in data if t.get("mentions", 0) >= MENTION_THRESHOLD]

    html = build_alert_email(spikes, history)
    send_email("🚨 WSB Buy/Sell Signal Report (7-Day Avg)", html)

if __name__ == "__main__":
    run_alert()
