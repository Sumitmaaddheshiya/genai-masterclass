import os
import sys
import csv
import json
import hmac
import hashlib
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify, send_file, send_from_directory, render_template_string
from dotenv import load_dotenv

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Load environment variables
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REGISTRATIONS_JSONL = os.path.join(BASE_DIR, "registrations.jsonl")
REGISTRATIONS_CSV = os.path.join(BASE_DIR, "registrations.csv")

app = Flask(__name__, static_folder=BASE_DIR)

# ─── Configuration ─────────────────────────────────────────────────────────────
ENABLE_PAYMENTS         = os.getenv("ENABLE_PAYMENTS", "false").lower() == "true"
ENABLE_EMAILS           = os.getenv("ENABLE_EMAILS", "false").lower() == "true"

SMTP_HOST               = os.getenv("SMTP_HOST", "smtp.sendgrid.net")
SMTP_PORT               = int(os.getenv("SMTP_PORT", 587))
SMTP_USER               = os.getenv("SMTP_USER")
SMTP_PASS               = os.getenv("SMTP_PASS")

RAZORPAY_KEY_ID         = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET     = os.getenv("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")

MEETING_LINK           = os.getenv("MEETING_LINK", os.getenv("ZOOM_LINK", "https://meet.google.com/xae-ejfw-ybm"))
ZOOM_LINK              = MEETING_LINK
WEBINAR_NAME           = os.getenv("WEBINAR_NAME", "GenAI Master Class")
WEBINAR_DATE           = os.getenv("WEBINAR_DATE", "Saturday, September 19 · 7:00-9:00 pm IST")
HOST_NAME              = os.getenv("HOST_NAME", "Akash Mohan")
COHOST_NAME            = os.getenv("COHOST_NAME", "Nikhil Mishra")


# ─── Data Storage Helper ───────────────────────────────────────────────────────
def save_registration(name: str, email: str, phone: str = "", payment_id: str = "DIRECT_FREE_OR_SANDBOX") -> dict:
    """Save an attendee record to JSONL and CSV."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    record = {
        "timestamp": now_str,
        "name": name.strip(),
        "email": email.strip().lower(),
        "phone": phone.strip(),
        "payment_id": payment_id,
        "webinar": WEBINAR_NAME,
        "date": WEBINAR_DATE
    }

    # Save to JSON Lines
    with open(REGISTRATIONS_JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    # Save to CSV
    csv_exists = os.path.exists(REGISTRATIONS_CSV)
    with open(REGISTRATIONS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "name", "email", "phone", "payment_id", "webinar", "date"])
        if not csv_exists:
            writer.writeheader()
        writer.writerow(record)

    return record


# ─── Email Sender ──────────────────────────────────────────────────────────────
def send_confirmation_email(customer_email: str, customer_name: str) -> bool:
    """Sends the Zoom access link to an attendee."""
    if not ENABLE_EMAILS or not SMTP_USER or not SMTP_PASS:
        print(f"ℹ️  Email delivery skipped (ENABLE_EMAILS={ENABLE_EMAILS}, SMTP_USER configured: {bool(SMTP_USER)})")
        return False

    msg = MIMEMultipart("alternative")
    msg["From"]    = f'"{WEBINAR_NAME}" <{SMTP_USER}>'
    msg["To"]      = customer_email
    msg["Subject"] = f"Access Confirmation: {WEBINAR_NAME}"

    html_body = f"""
    <html>
    <body style="font-family: 'DM Sans', Arial, sans-serif; background:#08090d; padding:30px; color:#f0f2f7;">
      <div style="max-width:600px; margin:auto; background:#121622; border-radius:14px; overflow:hidden; border:1px solid #1e2436;">
        <div style="background:#171c2b; padding:28px; text-align:center; border-bottom:1px solid #1e2436;">
          <h1 style="color:#00d294; margin:0; font-size:22px; letter-spacing:-0.02em;">{WEBINAR_NAME}</h1>
          <p style="color:#949db2; margin-top:6px; font-size:14px;">Registration Confirmed</p>
        </div>
        <div style="padding:28px;">
          <p style="font-size:15px; color:#f0f2f7;">Hello <strong>{customer_name}</strong>,</p>
          <p style="color:#949db2; line-height:1.6; font-size:14.5px;">
            You are officially registered for the <strong>{WEBINAR_NAME}</strong> with 
            <strong>Akash Mohan</strong> (Data Analyst at Pace Stock Broking Pvt Ltd) and 
            <strong>Nikhil Mishra</strong> (Ex-InfoEdge).
          </p>
          <div style="text-align:center; margin:26px 0;">
            <a href="{ZOOM_LINK}" 
               style="background:#00d294; color:#04120e; 
                      padding:14px 30px; border-radius:999px; text-decoration:none; 
                      font-size:15px; font-weight:bold; display:inline-block;">
              Join the Live Class &rarr;
            </a>
          </div>
          <div style="background:#0c0f17; border-left:3px solid #00d294; padding:14px; border-radius:6px;">
            <p style="margin:0; color:#f0f2f7; font-size:13.5px;"><strong>Schedule:</strong> {WEBINAR_DATE}</p>
            <p style="margin:6px 0 0; color:#f0f2f7; font-size:13.5px;"><strong>Access Link:</strong> <a href="{ZOOM_LINK}" style="color:#00d294;">{ZOOM_LINK}</a></p>
          </div>
          <p style="color:#949db2; font-size:13.5px; line-height:1.6; margin-top:20px;">
            Early joiners will receive access to the Power Prompt Framework template and working Python starter code.
          </p>
          <p style="color:#f0f2f7; margin-top:22px;">See you in the session.</p>
        </div>
      </div>
    </body>
    </html>
    """

    plain_body = f"""Hello {customer_name},

Your registration is confirmed for {WEBINAR_NAME}.
Instructors: Akash Mohan (Data Analyst at Pace Stock Broking Pvt Ltd) & Nikhil Mishra (Ex-InfoEdge).

Schedule: {WEBINAR_DATE}
Zoom Link: {ZOOM_LINK}

See you in the live session.
"""

    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        print(f"✅ Confirmation email sent to {customer_email}")
        return True
    except Exception as e:
        print(f"❌ Error sending email to {customer_email}: {e}")
        return False


# ─── Frontend Routes ───────────────────────────────────────────────────────────
@app.route("/")
def index():
    """Serves the main sales and registration page."""
    index_path = os.path.join(BASE_DIR, "index.html")
    if not os.path.exists(index_path):
        # Fallback to fwddata if not yet moved
        alt_path = os.path.join(BASE_DIR, "fwddata", "index.html")
        if os.path.exists(alt_path):
            index_path = alt_path
    return send_file(index_path)


@app.route("/poster.jpg")
def poster():
    """Serves the promotional poster."""
    poster_path = os.path.join(BASE_DIR, "poster.jpg")
    if not os.path.exists(poster_path):
        poster_path = os.path.join(BASE_DIR, "fwddata", "poster.jpg")
    return send_file(poster_path, mimetype="image/jpeg")


# ─── Registration Endpoint (Instant Capture) ──────────────────────────────────
@app.route("/register", methods=["POST"])
def register():
    """Direct registration submission (saves attendee and confirms spot)."""
    try:
        data = request.get_json(silent=True) or request.form
        name = data.get("name", "").strip()
        email = data.get("email", "").strip()
        phone = data.get("phone", "").strip()

        if not name or not email:
            return jsonify({"status": "error", "error": "Name and Email are required"}), 400

        record = save_registration(name, email, phone, payment_id="CONFIRMED_RESERVATION")
        print(f"🎉 New attendee registered: {name} <{email}> (Phone: {phone})")

        # Try sending email if SMTP is configured
        if ENABLE_EMAILS:
            send_confirmation_email(email, name)

        return jsonify({
            "status": "success",
            "message": "Spot confirmed successfully!",
            "webinar": WEBINAR_NAME,
            "date": WEBINAR_DATE,
            "attendee": {"name": name, "email": email}
        }), 200

    except Exception as e:
        print(f"❌ Error in /register: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


# ─── Razorpay Order Endpoint ───────────────────────────────────────────────────
@app.route("/create-order", methods=["POST"])
def create_order():
    """
    Creates a Razorpay order if payments are enabled.
    If payments are deferred/disabled, seamlessly directs to /register.
    """
    data = request.get_json(silent=True) or {}
    name  = data.get("name", "")
    email = data.get("email", "")
    phone = data.get("phone", "")

    # If payments are toggled off, record directly as successful reservation
    if not ENABLE_PAYMENTS:
        save_registration(name, email, phone, payment_id="FREE_RSVP")
        if ENABLE_EMAILS:
            send_confirmation_email(email, name)
        return jsonify({
            "status": "sandbox_success",
            "message": "Reservation confirmed directly without payment gateway.",
            "direct": True
        }), 200

    # If payments are enabled, invoke Razorpay
    try:
        import razorpay
        client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

        order = client.order.create({
            "amount":   4900,  # ₹49 in paise
            "currency": "INR",
            "receipt":  f"webinar_{email[:20]}",
            "notes": {
                "name":    name,
                "email":   email,
                "phone":   phone,
                "webinar": WEBINAR_NAME
            }
        })

        return jsonify({
            "order_id": order["id"],
            "amount":   order["amount"],
            "currency": order["currency"],
            "key_id":   RAZORPAY_KEY_ID,
            "direct":   False
        }), 200

    except Exception as e:
        print(f"❌ Error creating Razorpay order: {e}")
        return jsonify({"error": str(e)}), 500


# ─── Razorpay Webhook Endpoint ─────────────────────────────────────────────────
@app.route("/webhook", methods=["POST"])
def razorpay_webhook():
    payload_body       = request.get_data()
    received_signature = request.headers.get("X-Razorpay-Signature", "")

    if RAZORPAY_WEBHOOK_SECRET:
        expected_signature = hmac.new(
            RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
            payload_body,
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected_signature, received_signature):
            print("❌ Invalid webhook signature")
            return jsonify({"status": "invalid signature"}), 400

    try:
        event = json.loads(payload_body)
    except json.JSONDecodeError:
        return jsonify({"status": "bad json"}), 400

    event_type = event.get("event")
    print(f"📩 Razorpay event: {event_type}")

    if event_type in ("payment.captured", "order.paid"):
        try:
            payment        = event["payload"]["payment"]["entity"]
            payment_id     = payment.get("id", "RZP_PAYMENT")
            notes          = payment.get("notes", {})
            customer_email = notes.get("email") or payment.get("email")
            customer_name  = notes.get("name", "there")
            customer_phone = notes.get("phone", payment.get("contact", ""))

            save_registration(customer_name, customer_email, customer_phone, payment_id=payment_id)
            if customer_email and ENABLE_EMAILS:
                send_confirmation_email(customer_email, customer_name)

        except Exception as e:
            print(f"❌ Error handling webhook event: {e}")

    return jsonify({"status": "received"}), 200


# ─── Admin Dashboard & Attendee Export ─────────────────────────────────────────
@app.route("/admin")
def admin_dashboard():
    """A sleek attendee management dashboard for Akash Mohan & Nikhil Mishra."""
    attendees = []
    if os.path.exists(REGISTRATIONS_JSONL):
        with open(REGISTRATIONS_JSONL, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        attendees.append(json.loads(line))
                    except Exception:
                        pass
    attendees.reverse()  # Newest first

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>Admin Dashboard — {WEBINAR_NAME}</title>
      <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
      <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'DM Sans', sans-serif; background: #07090e; color: #f0f3f8; padding: 40px 20px; }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; border-bottom: 1px solid #1e2436; padding-bottom: 20px; }}
        .title h1 {{ font-size: 22px; color: #00d294; letter-spacing: -0.02em; }}
        .title p {{ font-size: 13.5px; color: #949db2; margin-top: 4px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }}
        .stat-card {{ background: #121622; border: 1px solid #1e2436; border-radius: 12px; padding: 20px; }}
        .stat-label {{ font-size: 11.5px; color: #636c82; font-family: 'JetBrains Mono', monospace; text-transform: uppercase; letter-spacing: 0.08em; }}
        .stat-val {{ font-size: 28px; font-weight: 800; color: #f0f3f8; margin-top: 8px; font-family: 'JetBrains Mono', monospace; }}
        .btn {{ display: inline-block; background: #00d294; color: #04120e; font-weight: 700; text-decoration: none; padding: 10px 22px; border-radius: 999px; font-size: 13.5px; transition: transform 0.2s; }}
        .btn:hover {{ transform: translateY(-2px); }}
        table {{ width: 100%; border-collapse: collapse; background: #121622; border-radius: 12px; overflow: hidden; border: 1px solid #1e2436; }}
        th, td {{ padding: 14px 18px; text-align: left; font-size: 13.5px; border-bottom: 1px solid #1e2436; }}
        th {{ background: #171c2b; color: #00d294; font-weight: 600; font-size: 11.5px; font-family: 'JetBrains Mono', monospace; text-transform: uppercase; }}
        tr:hover {{ background: rgba(0, 210, 148, 0.02); }}
        .badge {{ background: rgba(0, 210, 148, 0.12); color: #00d294; padding: 4px 10px; border-radius: 50px; font-size: 11.5px; font-weight: 600; font-family: 'JetBrains Mono', monospace; }}
        .empty {{ text-align: center; padding: 50px; color: #636c82; font-size: 15px; }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <div class="title">
            <h1>{WEBINAR_NAME} — Attendee Portal</h1>
            <p>Instructors: Akash Mohan (Pace Stock Broking) &amp; Nikhil Mishra (Ex-InfoEdge) &bull; Schedule: {WEBINAR_DATE}</p>
          </div>
          <div>
            <a href="/admin/export-csv" class="btn">Export CSV &rarr;</a>
          </div>
        </div>

        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-label">Total Registrations</div>
            <div class="stat-val">{len(attendees)}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Scheduled Date</div>
            <div class="stat-val" style="font-size:18px; color:#00d4ff; margin-top:14px;">27 Sep 2026</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">System Mode</div>
            <div class="stat-val" style="font-size:18px; color:#34d399; margin-top:14px;">{'Live Razorpay' if ENABLE_PAYMENTS else 'Direct RSVP Mode'}</div>
          </div>
        </div>

        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Date & Time</th>
              <th>Name</th>
              <th>Email</th>
              <th>Phone</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {''.join(f'''<tr>
              <td>{i+1}</td>
              <td style="color:#888;">{a.get("timestamp", "-")}</td>
              <td><strong>{a.get("name", "-")}</strong></td>
              <td><a href="mailto:{a.get("email")}" style="color:#00d4ff; text-decoration:none;">{a.get("email", "-")}</a></td>
              <td>{a.get("phone", "-")}</td>
              <td><span class="badge">Confirmed</span></td>
            </tr>''' for i, a in enumerate(attendees)) if attendees else '<tr><td colspan="6" class="empty">No registrations yet. Submit the form on the landing page to test!</td></tr>'}
          </tbody>
        </table>
      </div>
    </body>
    </html>
    """
    return render_template_string(html)


@app.route("/admin/export-csv")
def export_csv():
    """Direct CSV download of all attendees."""
    if not os.path.exists(REGISTRATIONS_CSV):
        # Create an empty CSV with header
        with open(REGISTRATIONS_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp", "name", "email", "phone", "payment_id", "webinar", "date"])
            writer.writeheader()
    return send_file(REGISTRATIONS_CSV, as_attachment=True, download_name="genai_webinar_attendees.csv", mimetype="text/csv")


# ─── Health Check ──────────────────────────────────────────────────────────────
@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "webinar": WEBINAR_NAME,
        "host": HOST_NAME,
        "cohost": COHOST_NAME,
        "payments_enabled": ENABLE_PAYMENTS,
        "emails_enabled": ENABLE_EMAILS
    }), 200


# ─── App Runner ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    print(f"""
+------------------------------------------------------+
|   [WEBINAR SERVER ACTIVE]
|   Webinar: {WEBINAR_NAME}
|   Hosts:   {HOST_NAME} & {COHOST_NAME} (Ex-InfoEdge)
+------------------------------------------------------+
|   Landing Page: http://localhost:{port}
|   Admin Portal: http://localhost:{port}/admin
|   Mode:         {'Live Payments' if ENABLE_PAYMENTS else 'Direct RSVP Mode (Ready for testing)'}
+------------------------------------------------------+
    """)
    app.run(host="0.0.0.0", port=port, debug=debug)
