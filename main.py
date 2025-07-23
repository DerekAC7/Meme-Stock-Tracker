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
TO_EMAIL = GMAIL_ADDRESS

MENTION_THRESHOLD = 300        # Minimum mentions for any signal
BUY_LOWER = 1.3                 # Buy if ≥ 1.3× avg and < 1.6×
SELL_THRESHOLD = 1.6            # Sell if ≥ 1.6× avg OR big drop
DROP_THRESHOLD = 0.8            # Sell if today < 80% of yesterday after spike
HISTORY_FILE = "history.csv"
APE_URL = "https://apewisdom.io/api/v1.0/filter/all-stocks/page/1"
# ============================ #

def fetch_mentions():
    try:
        resp = requests.get(APE_URL)
        return resp.json().get('results', [])
    except Exception as e:
        print(f"❌ Failed to fetch ApeWisdom data: {e}", flush=True)
        return []

def load_history():
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
    today = datetime.utcnow()
    past_week = today - timedelta(days=7)

    mentions = [
        h["mentions"]
        for h in history.get(ticker, [])
        if h["date"] >= past_week
    ]

    return sum(mentions) / len(mentions) if mentions else 0

def get_yesterday_mentions(history, ticker):
    if ticker not in history or not history[ticker]:
        return 0
    sorted_entries = sorted(history[ticker], key=lambda x: x["date"], reverse=True)
    return sorted_entries[0]["mentions"] if sorted_entries else 0

def build_alert_email(spikes, history):
    if not spikes:
        return "<p>No significant WSB mention spikes today.</p>"

    buy_lines = ""
    sell_lines = ""
    summary_lines = ""

    # Rank by mentions to detect top 3 spikes
    sorted_spikes = sorted(spikes, key=lambda x: x.get("mentions", 0), reverse=True)
    top_spikes = {s.get("ticker") for s in sorted_spikes[:3]}

    for s in spikes:
        ticker = s.get("ticker", "???")
        mentions = s.get("mentions", 0)
        avg_7d = compute_7day_average(history, ticker)
        ratio = mentions / avg_7d if avg_7d else 0

        yesterday_mentions = get_yesterday_mentions(history, ticker)
        day_change = (mentions - yesterday_mentions) / yesterday_mentions * 100 if yesterday_mentions else 0
        trend_text = f"{day_change:+.1f}%" if yesterday_mentions else "n/a"

        ratio_text = f"{ratio:.1f}× avg" if avg_7d else "no avg"

        # SELL LOGIC
        if (
            (ratio >= SELL_THRESHOLD and mentions >= MENTION_THRESHOLD and (mentions >= 800 or ticker in top_spikes))
            or (yesterday_mentions and mentions < yesterday_mentions * DROP_THRESHOLD)
        ):
            sell_lines += f"⚠️ <b>Sell Signal:</b> {ticker} — {mentions} vs {avg_7d:.0f} ({ratio_text}, {trend_text} vs yesterday)<br>"

        # BUY LOGIC
        elif (
            ratio >= BUY_LOWER and ratio < SELL_THRESHOLD
            and mentions >= MENTION_THRESHOLD
            and day_change > 0
        ):
            buy_lines += f"🚀 <b>Buy Signal:</b> {ticker} — {mentions} vs {avg_7d:.0f} ({ratio_text}, {trend_text} vs yesterday)<br>"

        # SUMMARY
        summary_lines += f"📊 {ticker}: {mentions} mentions (7d avg: {avg_7d:.0f}, {trend_text} vs yesterday)<br>"

    html = ""
    if buy_lines:
        html += f"<h3>🚀 Buy Alerts</h3>{buy_lines}<br>"
    if sell_lines:
        html += f"<h3>⚠️ Sell Alerts</h3>{sell_lines}<br>"
    html += f"<h3>📊 Daily Summary (8 AM PT)</h3>{summary_lines}"
    html += "<p style='font-size:12px;color:gray;'>Auto-generated with momentum + spike logic for profit-taking.</p>"
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
        print("✅ Email sent successfully.", flush=True)
    except Exception as e:
        print(f"❌ Failed to send email: {e}", flush=True)

def run_alert():
    data = fetch_mentions()
    if not data:
        print("No data from API — aborting run.", flush=True)
        return

    save_today_mentions(data)
    history = load_history()

    spikes = [t for t in data if t.get("mentions", 0) >= MENTION_THRESHOLD]

    html = build_alert_email(spikes, history)
    send_email("🚨 WSB Buy/Sell Signal Report (Momentum + Spike Logic)", html)

if __name__ == "__main__":
    run_alert()
