import os
import sys
import csv
import json
import uuid
import hmac
import base64
import hashlib
import smtplib
import requests
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify, send_file, send_from_directory, render_template_string, redirect, Response
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
PAYMENT_GATEWAY         = os.getenv("PAYMENT_GATEWAY", "PHONEPE").upper()  # "PHONEPE" or "RAZORPAY"
WEBINAR_PRICE_INR       = int(os.getenv("WEBINAR_PRICE_INR", "49"))

# PhonePe Configuration
PHONEPE_MERCHANT_ID     = os.getenv("PHONEPE_MERCHANT_ID", "PGTESTPAYUAT")
PHONEPE_SALT_KEY        = os.getenv("PHONEPE_SALT_KEY", "099eb0cd-02cf-4e2a-8aca-3e6c6aff0399")
PHONEPE_SALT_INDEX      = os.getenv("PHONEPE_SALT_INDEX", "1")
PHONEPE_ENV             = os.getenv("PHONEPE_ENV", "UAT").upper()  # "UAT" or "PROD"
PHONEPE_BASE_URL        = "https://api.phonepe.com/apis/hermes" if PHONEPE_ENV == "PROD" else "https://api-preprod.phonepe.com/apis/pg-sandbox"

# In-memory transaction cache for pending checkouts
PENDING_TRANSACTIONS = {}

# Razorpay Configuration
RAZORPAY_KEY_ID         = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET     = os.getenv("RAZORPAY_KEY_SECRET", "")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

# Email / SMTP Configuration
SMTP_HOST               = os.getenv("SMTP_HOST", "smtp.sendgrid.net")
SMTP_PORT               = int(os.getenv("SMTP_PORT", 587))
SMTP_USER               = os.getenv("SMTP_USER")
SMTP_PASS               = os.getenv("SMTP_PASS")

# Webinar Metadata
MEETING_LINK            = os.getenv("MEETING_LINK", os.getenv("ZOOM_LINK", "https://meet.google.com/xae-ejfw-ybm"))
ZOOM_LINK               = MEETING_LINK
WEBINAR_NAME            = os.getenv("WEBINAR_NAME", "GenAI Master Class")
WEBINAR_DATE            = os.getenv("WEBINAR_DATE", "Sunday, 27 September 2026 · 7:00-9:00 pm IST")
HOST_NAME               = os.getenv("HOST_NAME", "Akash Mohan")
COHOST_NAME             = os.getenv("COHOST_NAME", "Nikhil Mishra")
SUPPORT_EMAIL           = os.getenv("SUPPORT_EMAIL", "contact@analystworld.in")
SUPPORT_PHONE           = os.getenv("SUPPORT_PHONE", "+91 98765 43210")
WHATSAPP_LINK           = os.getenv("WHATSAPP_LINK", "https://chat.whatsapp.com/invite/genai-masterclass")
ADMIN_PASSWORD          = os.getenv("ADMIN_PASSWORD", "")  # Optional: secure admin portal on deployed URL


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
    """Sends the Google Meet access link to an attendee."""
    if not ENABLE_EMAILS or not SMTP_USER or not SMTP_PASS:
        return False

    msg = MIMEMultipart("alternative")
    msg["From"]    = f'"{WEBINAR_NAME}" <{SMTP_USER}>'
    msg["To"]      = customer_email
    msg["Subject"] = f"Access Confirmation: {WEBINAR_NAME}"

    html_body = f"""
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background:#f8fafc; padding:30px; color:#0f172a;">
      <div style="max-width:600px; margin:auto; background:#ffffff; border-radius:12px; overflow:hidden; border:1px solid #e2e8f0; box-shadow:0 4px 12px rgba(0,0,0,0.05);">
        <div style="background:#1d4ed8; padding:28px; text-align:center;">
          <h1 style="color:#ffffff; margin:0; font-size:22px; font-weight:700;">{WEBINAR_NAME}</h1>
          <p style="color:#bfdbfe; margin-top:6px; font-size:14px;">Registration Confirmed</p>
        </div>
        <div style="padding:28px;">
          <p style="font-size:15px; color:#0f172a;">Hello <strong>{customer_name}</strong>,</p>
          <p style="color:#475569; line-height:1.6; font-size:14.5px;">
            You are officially registered for the <strong>{WEBINAR_NAME}</strong> with 
            <strong>Akash Mohan</strong> (Data Analyst at Pace Stock Broking Pvt Ltd) and 
            <strong>Nikhil Mishra</strong> (Ex-InfoEdge).
          </p>
          <div style="text-align:center; margin:26px 0;">
            <a href="{MEETING_LINK}" 
               style="background:#1d4ed8; color:#ffffff; 
                      padding:14px 30px; border-radius:8px; text-decoration:none; 
                      font-size:15px; font-weight:700; display:inline-block;">
              Join Live on Google Meet &rarr;
            </a>
          </div>
          <div style="background:#f1f5f9; border-left:4px solid #1d4ed8; padding:14px; border-radius:6px;">
            <p style="margin:0; color:#0f172a; font-size:13.5px;"><strong>Schedule:</strong> {WEBINAR_DATE}</p>
            <p style="margin:6px 0 0; color:#0f172a; font-size:13.5px;"><strong>Access Link:</strong> <a href="{MEETING_LINK}" style="color:#1d4ed8;">{MEETING_LINK}</a></p>
          </div>
          <p style="color:#64748b; font-size:13px; line-height:1.6; margin-top:20px;">
            Please join 5 minutes early. Starter Python code and architectural diagrams will be shared at the start of the session.
          </p>
          <p style="color:#0f172a; margin-top:22px; font-weight:500;">See you inside.</p>
        </div>
      </div>
    </body>
    </html>
    """

    plain_body = f"""Hello {customer_name},

Your registration is confirmed for {WEBINAR_NAME}.
Instructors: Akash Mohan (Data Analyst at Pace Stock Broking Pvt Ltd) & Nikhil Mishra (Ex-InfoEdge).

Schedule: {WEBINAR_DATE}
Google Meet Link: {MEETING_LINK}

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
        return True
    except Exception as e:
        print(f"Error sending email to {customer_email}: {e}")
        return False


# ─── Frontend Routes ───────────────────────────────────────────────────────────
@app.route("/")
def index():
    """Serves the main sales and registration page."""
    index_path = os.path.join(BASE_DIR, "index.html")
    if not os.path.exists(index_path):
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


# ─── Registration Endpoint (Direct RSVP & PhonePe Flow) ────────────────────────
@app.route("/register", methods=["POST"])
def register():
    """
    Direct registration submission.
    - If ENABLE_PAYMENTS=true and PAYMENT_GATEWAY=PHONEPE: Initiates PhonePe checkout.
    - Otherwise: Confirms spot immediately (free RSVP mode).
    """
    try:
        data = request.get_json(silent=True) or request.form
        name = data.get("name", "").strip()
        email = data.get("email", "").strip()
        phone = data.get("phone", "").strip()

        if not name or not email:
            return jsonify({"status": "error", "error": "Name and Email are required"}), 400

        # If payments are enabled with PhonePe:
        if ENABLE_PAYMENTS and PAYMENT_GATEWAY == "PHONEPE":
            tx_id = f"MT{int(datetime.now().timestamp())}{uuid.uuid4().hex[:4].upper()}"
            user_id = f"U{uuid.uuid4().hex[:6].upper()}"

            base_url = request.host_url.rstrip("/")
            if "onrender.com" in base_url and base_url.startswith("http://"):
                base_url = base_url.replace("http://", "https://")

            redirect_url = f"{base_url}/phonepe/callback"
            callback_url = f"{base_url}/phonepe/webhook"

            payload = {
                "merchantId": PHONEPE_MERCHANT_ID,
                "merchantTransactionId": tx_id,
                "merchantUserId": user_id,
                "amount": WEBINAR_PRICE_INR * 100,  # in paise
                "redirectUrl": redirect_url,
                "redirectMode": "POST",
                "callbackUrl": callback_url,
                "mobileNumber": phone or "9999999999",
                "paymentInstrument": {
                    "type": "PAY_PAGE"
                }
            }

            # Cache attendee metadata with transaction ID
            PENDING_TRANSACTIONS[tx_id] = {
                "name": name,
                "email": email,
                "phone": phone
            }

            payload_json = json.dumps(payload)
            base64_payload = base64.b64encode(payload_json.encode("utf-8")).decode("utf-8")
            hash_input = base64_payload + "/pg/v1/pay" + PHONEPE_SALT_KEY
            checksum = hashlib.sha256(hash_input.encode("utf-8")).hexdigest() + "###" + PHONEPE_SALT_INDEX

            req_headers = {
                "Content-Type": "application/json",
                "X-VERIFY": checksum
            }

            try:
                res = requests.post(f"{PHONEPE_BASE_URL}/pg/v1/pay", json={"request": base64_payload}, headers=req_headers, timeout=10)
                res_data = res.json()
                if res_data.get("success"):
                    pay_url = res_data["data"]["instrumentResponse"]["redirectInfo"]["url"]
                    return jsonify({
                        "status": "success",
                        "direct": False,
                        "redirect_url": pay_url
                    }), 200
                else:
                    return jsonify({
                        "status": "error",
                        "error": res_data.get("message", "Payment initiation failed with PhonePe.")
                    }), 400
            except Exception as pe:
                print(f"PhonePe API Error: {pe}")
                return jsonify({"status": "error", "error": f"PhonePe communication error: {pe}"}), 500

        # Direct RSVP mode (Instant confirmation)
        record = save_registration(name, email, phone, payment_id="CONFIRMED_RESERVATION")
        print(f"Attendee registered: {name} <{email}> (Phone: {phone})")

        if ENABLE_EMAILS:
            send_confirmation_email(email, name)

        return jsonify({
            "status": "success",
            "direct": True,
            "message": "Spot confirmed successfully!",
            "webinar": WEBINAR_NAME,
            "date": WEBINAR_DATE,
            "attendee": {"name": name, "email": email}
        }), 200

    except Exception as e:
        print(f"Error in /register: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


# ─── PhonePe Callback & Webhook ───────────────────────────────────────────────
@app.route("/phonepe/callback", methods=["POST", "GET"])
def phonepe_callback():
    """Handles browser redirect back from PhonePe after checkout."""
    form_data = request.form.to_dict() or request.args.to_dict()
    code = form_data.get("code")
    merchant_id = form_data.get("merchantId", PHONEPE_MERCHANT_ID)
    tx_id = form_data.get("transactionId") or form_data.get("merchantTransactionId")

    is_success = False

    # Verify status via PhonePe S2S Status Check API
    if tx_id:
        try:
            status_url = f"{PHONEPE_BASE_URL}/pg/v1/status/{merchant_id}/{tx_id}"
            hash_input = f"/pg/v1/status/{merchant_id}/{tx_id}" + PHONEPE_SALT_KEY
            checksum = hashlib.sha256(hash_input.encode("utf-8")).hexdigest() + "###" + PHONEPE_SALT_INDEX
            headers = {
                "Content-Type": "application/json",
                "X-VERIFY": checksum,
                "X-MERCHANT-ID": merchant_id
            }
            res = requests.get(status_url, headers=headers, timeout=10)
            res_data = res.json()
            if res_data.get("code") == "PAYMENT_SUCCESS":
                is_success = True
        except Exception as e:
            print(f"PhonePe status check error: {e}")
            if code == "PAYMENT_SUCCESS":
                is_success = True

    if is_success or code == "PAYMENT_SUCCESS":
        attendee = PENDING_TRANSACTIONS.get(tx_id, {"name": "Attendee", "email": "", "phone": ""})
        name = attendee.get("name") or "Attendee"
        email = attendee.get("email") or ""
        phone = attendee.get("phone") or ""

        save_registration(name, email, phone, payment_id=tx_id or "PHONEPE_PAID")
        if email and ENABLE_EMAILS:
            send_confirmation_email(email, name)

        return render_template_string(PAYMENT_SUCCESS_PAGE, name=name, email=email, tx_id=tx_id)
    else:
        return render_template_string(PAYMENT_FAILED_PAGE, tx_id=tx_id)


@app.route("/phonepe/webhook", methods=["POST"])
def phonepe_webhook():
    """Handles S2S server-to-server webhook callback from PhonePe."""
    try:
        req_data = request.get_json(silent=True) or {}
        b64_response = req_data.get("response")
        if b64_response:
            decoded = json.loads(base64.b64decode(b64_response).decode("utf-8"))
            tx_id = decoded.get("data", {}).get("merchantTransactionId")
            code = decoded.get("code")
            if code == "PAYMENT_SUCCESS" and tx_id:
                attendee = PENDING_TRANSACTIONS.get(tx_id, {})
                if attendee:
                    save_registration(attendee.get("name", ""), attendee.get("email", ""), attendee.get("phone", ""), payment_id=tx_id)
        return jsonify({"status": "received"}), 200
    except Exception as e:
        print(f"PhonePe webhook error: {e}")
        return jsonify({"status": "error"}), 400


# ─── Razorpay Endpoints (Alternative Option) ──────────────────────────────────
@app.route("/create-order", methods=["POST"])
def create_order():
    data = request.get_json(silent=True) or {}
    name  = data.get("name", "")
    email = data.get("email", "")
    phone = data.get("phone", "")

    if not ENABLE_PAYMENTS or PAYMENT_GATEWAY != "RAZORPAY":
        save_registration(name, email, phone, payment_id="FREE_RSVP")
        if ENABLE_EMAILS:
            send_confirmation_email(email, name)
        return jsonify({
            "status": "sandbox_success",
            "message": "Reservation confirmed directly.",
            "direct": True
        }), 200

    try:
        import razorpay
        client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
        order = client.order.create({
            "amount":   WEBINAR_PRICE_INR * 100,
            "currency": "INR",
            "receipt":  f"webinar_{email[:20]}",
            "notes": { "name": name, "email": email, "phone": phone, "webinar": WEBINAR_NAME }
        })
        return jsonify({
            "order_id": order["id"],
            "amount":   order["amount"],
            "currency": order["currency"],
            "key_id":   RAZORPAY_KEY_ID,
            "direct":   False
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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
            return jsonify({"status": "invalid signature"}), 400

    try:
        event = json.loads(payload_body)
    except json.JSONDecodeError:
        return jsonify({"status": "bad json"}), 400

    event_type = event.get("event")
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
            print(f"Razorpay webhook error: {e}")

    return jsonify({"status": "received"}), 200


# ─── Legal & Compliance Pages (Required for PhonePe Merchant Approval) ─────────
LEGAL_PAGE_LAYOUT = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ title }} &bull; GenAI Masterclass</title>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif; background: #ffffff; color: #0f172a; line-height: 1.65; }
    header { border-bottom: 1px solid #e2e8f0; padding: 18px 0; background: #ffffff; }
    .container { max-width: 800px; margin: 0 auto; padding: 0 24px; }
    .nav-row { display: flex; justify-content: space-between; align-items: center; }
    .nav-logo { font-size: 18px; font-weight: 800; color: #0f172a; text-decoration: none; }
    .nav-logo span { color: #1d4ed8; }
    .nav-back { font-size: 13.5px; font-weight: 600; color: #1d4ed8; text-decoration: none; }
    main { padding: 48px 0 80px; }
    h1 { font-size: 32px; font-weight: 800; color: #0f172a; margin-bottom: 10px; letter-spacing: -0.02em; }
    .meta-tag { font-size: 13px; color: #64748b; font-family: 'JetBrains Mono', monospace; margin-bottom: 30px; }
    h2 { font-size: 20px; font-weight: 700; color: #0f172a; margin: 28px 0 10px; }
    p, li { font-size: 15px; color: #334155; margin-bottom: 14px; }
    ul { padding-left: 24px; margin-bottom: 16px; }
    footer { border-top: 1px solid #e2e8f0; padding: 24px 0; text-align: center; font-size: 13px; color: #64748b; }
  </style>
</head>
<body>
  <header>
    <div class="container nav-row">
      <a href="/" class="nav-logo">GenAI<span>Masterclass</span></a>
      <a href="/" class="nav-back">&larr; Back to Masterclass</a>
    </div>
  </header>
  <main>
    <div class="container">
      <h1>{{ title }}</h1>
      <div class="meta-tag">Last updated: September 2026 &bull; Organizer: Akash Mohan &amp; Nikhil Mishra</div>
      {{ content|safe }}
    </div>
  </main>
  <footer>
    <div class="container">
      <p>&copy; 2026 GenAI Master Class &bull; All rights reserved.</p>
    </div>
  </footer>
</body>
</html>
"""

@app.route("/terms")
def terms_page():
    content = """
    <h2>1. Overview</h2>
    <p>This masterclass is organized by Akash Mohan (Data Analyst at Pace Stock Broking Pvt Ltd) and Nikhil Mishra (Ex-InfoEdge). By registering for the live session on Sunday, 27 September 2026 from 7:00 PM to 9:00 PM IST, you agree to these Terms and Conditions.</p>
    
    <h2>2. Nature of Service</h2>
    <p>GenAI Master Class is a live interactive technical workshop conducted over Google Meet. Attendees receive live instruction, code walkthroughs, starter templates, and Q&A interaction.</p>

    <h2>3. Attendee Conduct</h2>
    <p>Participants are expected to maintain professional etiquette during the session. Unsolicited marketing, spam, or disruptive behavior during the Google Meet call will result in immediate removal without refund.</p>

    <h2>4. Intellectual Property</h2>
    <p>Starter repositories and educational code provided during the workshop are licensed for personal learning and portfolio use. Commercial distribution or unauthorized resale of the session recording is prohibited.</p>

    <h2>5. Contact Information</h2>
    <p>For inquiries regarding these terms, please contact: <strong>contact@analystworld.in</strong>.</p>
    """
    return render_template_string(LEGAL_PAGE_LAYOUT, title="Terms & Conditions", content=content)


@app.route("/privacy")
def privacy_page():
    content = """
    <h2>1. Information We Collect</h2>
    <p>When you register for the GenAI Master Class, we collect your full name, email address, and optional phone number. When processing payments via PhonePe or Razorpay, payment details are processed through encrypted, PCI-DSS compliant payment gateways; we never store your credit card or UPI credentials.</p>

    <h2>2. Purpose of Use</h2>
    <p>Your details are used strictly to:
      <ul>
        <li>Deliver the Google Meet joining credentials and access link.</li>
        <li>Send event reminders, technical starter files, and prompt templates.</li>
        <li>Provide customer support regarding your registration.</li>
      </ul>
    </p>

    <h2>3. Data Protection & Sharing</h2>
    <p>We do not sell, rent, or trade your personal information with third parties. Your details remain confidential and are only accessed by the event organizers.</p>

    <h2>4. Data Retention</h2>
    <p>Attendee data is stored securely in compliance with applicable digital privacy standards. You may request deletion of your information at any time by emailing <strong>contact@analystworld.in</strong>.</p>
    """
    return render_template_string(LEGAL_PAGE_LAYOUT, title="Privacy Policy", content=content)


@app.route("/refund")
def refund_page():
    content = """
    <h2>1. Registration Fee</h2>
    <p>Registration fees for the GenAI Master Class (e.g. ₹49 early bird or standard access) are collected to cover cloud server costs and infrastructure access.</p>

    <h2>2. Cancellation Policy</h2>
    <p>If you are unable to attend the live workshop on Sunday, 27 September 2026, you may cancel your registration by emailing <strong>contact@analystworld.in</strong> at least 4 hours prior to the scheduled session start time (7:00 PM IST).</p>

    <h2>3. Refund Processing</h2>
    <p>Eligible refund requests will be processed within 5 to 7 business days directly to the original payment method (PhonePe, UPI, credit card, or net banking) via our payment gateway partner.</p>

    <h2>4. Session Rescheduling</h2>
    <p>In the unlikely event of session rescheduling due to technical or unforeseen circumstances, your registration will automatically carry forward to the next live cohort, or a full refund will be provided upon request.</p>
    """
    return render_template_string(LEGAL_PAGE_LAYOUT, title="Cancellation & Refund Policy", content=content)


@app.route("/contact")
def contact_page():
    content = f"""
    <h2>Event Organizers</h2>
    <p><strong>Akash Mohan</strong><br>Data Analyst at Pace Stock Broking Pvt Ltd</p>
    <p><strong>Nikhil Mishra</strong><br>GenAI Specialist &bull; Ex-InfoEdge</p>

    <h2>Official Communication</h2>
    <p><strong>Email:</strong> contact@analystworld.in</p>
    <p><strong>Support Phone:</strong> +91 98765 43210</p>
    <p><strong>Workshop Schedule:</strong> Sunday, 27 September 2026 &bull; 7:00 PM &ndash; 9:00 PM IST</p>
    <p><strong>Platform:</strong> Google Meet (<a href="{MEETING_LINK}" style="color:#1d4ed8;">Access Link</a>)</p>
    """
    return render_template_string(LEGAL_PAGE_LAYOUT, title="Contact Us", content=content)


# ─── Payment Success & Failed Templates ───────────────────────────────────────
PAYMENT_SUCCESS_PAGE = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Payment Successful &bull; GenAI Masterclass</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'DM Sans', -apple-system, sans-serif; background: #f8fafc; color: #0f172a; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 24px; }}
    .card {{ background: #ffffff; max-width: 540px; width: 100%; border: 1px solid #e2e8f0; border-radius: 16px; padding: 40px 32px; box-shadow: 0 10px 30px rgba(0,0,0,0.06); text-align: center; }}
    .badge {{ display: inline-block; background: #ecfdf5; color: #059669; font-size: 13px; font-weight: 700; padding: 6px 14px; border-radius: 50px; margin-bottom: 18px; border: 1px solid #a7f3d0; font-family: 'JetBrains Mono', monospace; }}
    h1 {{ font-size: 26px; font-weight: 800; color: #0f172a; margin-bottom: 10px; }}
    p {{ font-size: 15px; color: #475569; line-height: 1.6; margin-bottom: 24px; }}
    .info-box {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 18px; text-align: left; margin-bottom: 24px; font-size: 14px; }}
    .info-row {{ display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #edf2f7; }}
    .info-row:last-child {{ border-bottom: none; }}
    .info-label {{ color: #64748b; }}
    .info-val {{ font-weight: 600; color: #0f172a; }}
    .btn {{ display: block; width: 100%; padding: 14px; background: #1d4ed8; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 700; font-size: 15px; margin-bottom: 12px; }}
    .btn-sub {{ display: block; width: 100%; padding: 12px; background: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 14px; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="badge">&check; Payment Verified &bull; Confirmed</div>
    <h1>You are in the masterclass!</h1>
    <p>Thank you, <strong>{{{{ name }}}}</strong>. Your registration is officially locked for Sunday, 27 September at 7:00 PM IST.</p>
    
    <div class="info-box">
      <div class="info-row"><span class="info-label">Date &amp; Time</span><span class="info-val">{WEBINAR_DATE}</span></div>
      <div class="info-row"><span class="info-label">Platform</span><span class="info-val">Google Meet</span></div>
      <div class="info-row"><span class="info-label">Hosts</span><span class="info-val">Akash Mohan &amp; Nikhil Mishra</span></div>
      <div class="info-row"><span class="info-label">Transaction ID</span><span class="info-val" style="font-family:'JetBrains Mono',monospace;">{{{{ tx_id }}}}</span></div>
    </div>

    <a href="{MEETING_LINK}" target="_blank" class="btn">Join Google Meet Call &rarr;</a>
    <a href="{WHATSAPP_LINK}" target="_blank" class="btn-sub">Join VIP WhatsApp Community &rarr;</a>
  </div>
</body>
</html>
"""

PAYMENT_FAILED_PAGE = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Payment Incomplete &bull; GenAI Masterclass</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'DM Sans', sans-serif; background: #f8fafc; color: #0f172a; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 24px; }}
    .card {{ background: #ffffff; max-width: 500px; width: 100%; border: 1px solid #fecaca; border-radius: 16px; padding: 40px 32px; box-shadow: 0 10px 30px rgba(0,0,0,0.06); text-align: center; }}
    .badge {{ display: inline-block; background: #fef2f2; color: #dc2626; font-size: 13px; font-weight: 700; padding: 6px 14px; border-radius: 50px; margin-bottom: 18px; }}
    h1 {{ font-size: 24px; font-weight: 800; color: #0f172a; margin-bottom: 10px; }}
    p {{ font-size: 15px; color: #475569; line-height: 1.6; margin-bottom: 24px; }}
    .btn {{ display: block; width: 100%; padding: 14px; background: #1d4ed8; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 700; font-size: 15px; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="badge">&times; Payment Not Completed</div>
    <h1>Payment Incomplete</h1>
    <p>Your payment attempt could not be verified or was cancelled. If money was deducted, it will be refunded to your account automatically within 48 hours.</p>
    <a href="/#register" class="btn">Try Registering Again &rarr;</a>
  </div>
</body>
</html>
"""


def check_admin_access():
    """Validates admin access via query key (?key=XYZ) or HTTP Basic Auth."""
    if not ADMIN_PASSWORD:
        return True
    token = request.args.get("key") or request.args.get("password")
    if token and token == ADMIN_PASSWORD:
        return True
    auth = request.authorization
    if auth and (auth.password == ADMIN_PASSWORD or auth.username == ADMIN_PASSWORD):
        return True
    return False


# ─── Admin Dashboard & Attendee Export ─────────────────────────────────────────
@app.route("/admin")
def admin_dashboard():
    """Attendee management dashboard for Akash Mohan & Nikhil Mishra."""
    if not check_admin_access():
        return Response(
            "Access Denied: Please provide the admin password.",
            401,
            {"WWW-Authenticate": 'Basic realm="Admin Portal Login"'}
        )

    attendees = []
    if os.path.exists(REGISTRATIONS_JSONL):
        with open(REGISTRATIONS_JSONL, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        attendees.append(json.loads(line))
                    except Exception:
                        pass
    attendees.reverse()

    admin_key = request.args.get("key", "")
    export_url = f"/admin/export-csv?key={admin_key}" if admin_key else "/admin/export-csv"

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>Admin Dashboard &bull; {WEBINAR_NAME}</title>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
      <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'DM Sans', sans-serif; background: #ffffff; color: #0f172a; padding: 40px 20px; }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; border-bottom: 1px solid #e2e8f0; padding-bottom: 20px; flex-wrap: wrap; gap: 16px; }}
        .title h1 {{ font-size: 22px; color: #1d4ed8; letter-spacing: -0.02em; font-weight: 800; }}
        .title p {{ font-size: 13.5px; color: #64748b; margin-top: 4px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }}
        .stat-card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; }}
        .stat-label {{ font-size: 11.5px; color: #64748b; font-family: 'JetBrains Mono', monospace; text-transform: uppercase; letter-spacing: 0.08em; }}
        .stat-val {{ font-size: 28px; font-weight: 800; color: #0f172a; margin-top: 8px; font-family: 'JetBrains Mono', monospace; }}
        .controls {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; gap: 12px; flex-wrap: wrap; }}
        .search-box {{ flex: 1; min-width: 260px; padding: 10px 14px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; font-family: inherit; }}
        .search-box:focus {{ outline: none; border-color: #1d4ed8; }}
        .btn {{ display: inline-block; background: #1d4ed8; color: #ffffff; font-weight: 700; text-decoration: none; padding: 10px 20px; border-radius: 8px; font-size: 13.5px; border: none; cursor: pointer; }}
        .btn-outline {{ background: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; }}
        table {{ width: 100%; border-collapse: collapse; background: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; }}
        th, td {{ padding: 14px 18px; text-align: left; font-size: 13.5px; border-bottom: 1px solid #e2e8f0; }}
        th {{ background: #f1f5f9; color: #1e293b; font-weight: 700; font-size: 11.5px; font-family: 'JetBrains Mono', monospace; text-transform: uppercase; }}
        tr:hover {{ background: #f8fafc; }}
        .badge {{ background: #eff6ff; color: #1d4ed8; padding: 4px 10px; border-radius: 50px; font-size: 11.5px; font-weight: 600; font-family: 'JetBrains Mono', monospace; }}
        .empty {{ text-align: center; padding: 50px; color: #64748b; font-size: 15px; }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <div class="title">
            <h1>{WEBINAR_NAME} &bull; Attendee Portal</h1>
            <p>Hosts: Akash Mohan (Pace Stock Broking) &amp; Nikhil Mishra (Ex-InfoEdge) &bull; Schedule: {WEBINAR_DATE}</p>
          </div>
          <div style="display:flex; gap:10px;">
            <a href="{export_url}" class="btn">Export CSV &rarr;</a>
            <button onclick="window.location.reload()" class="btn btn-outline">Refresh</button>
          </div>
        </div>

        <div class="stats-grid">
          <div class="stat-card">
            <div class="stat-label">Total Registrations</div>
            <div class="stat-val">{len(attendees)}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Scheduled Date</div>
            <div class="stat-val" style="font-size:18px; color:#1d4ed8; margin-top:14px;">27 Sep 2026</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">System Mode</div>
            <div class="stat-val" style="font-size:18px; color:#059669; margin-top:14px;">{'Live PhonePe' if (ENABLE_PAYMENTS and PAYMENT_GATEWAY == 'PHONEPE') else ('Live Razorpay' if ENABLE_PAYMENTS else 'Direct RSVP Mode')}</div>
          </div>
        </div>

        <div class="controls">
          <input type="text" id="searchInput" class="search-box" placeholder="Search attendees by name, email, or phone..." onkeyup="filterAttendees()">
        </div>

        <table id="attendeesTable">
          <thead>
            <tr>
              <th>#</th>
              <th>Date &amp; Time</th>
              <th>Name</th>
              <th>Email</th>
              <th>Phone</th>
              <th>Payment / Status</th>
            </tr>
          </thead>
          <tbody>
            {''.join(f'''<tr class="attendee-row">
              <td>{i+1}</td>
              <td style="color:#64748b;">{a.get("timestamp", "-")}</td>
              <td class="col-name"><strong>{a.get("name", "-")}</strong></td>
              <td class="col-email"><a href="mailto:{a.get("email")}" style="color:#1d4ed8; text-decoration:none;">{a.get("email", "-")}</a></td>
              <td class="col-phone">{a.get("phone", "-")}</td>
              <td><span class="badge">{a.get("payment_id", "CONFIRMED")[:18]}</span></td>
            </tr>''' for i, a in enumerate(attendees)) if attendees else '<tr><td colspan="6" class="empty">No registrations yet.</td></tr>'}
          </tbody>
        </table>
      </div>

      <script>
        function filterAttendees() {{
          const input = document.getElementById('searchInput').value.toLowerCase();
          const rows = document.querySelectorAll('.attendee-row');
          rows.forEach(row => {{
            const text = row.innerText.toLowerCase();
            row.style.display = text.includes(input) ? '' : 'none';
          }});
        }}
      </script>
    </body>
    </html>
    """
    return render_template_string(html)


@app.route("/admin/export-csv")
def export_csv():
    """Direct CSV download of all attendees."""
    if not check_admin_access():
        return Response(
            "Access Denied: Please provide the admin password.",
            401,
            {"WWW-Authenticate": 'Basic realm="Admin Portal Login"'}
        )

    if not os.path.exists(REGISTRATIONS_CSV):
        with open(REGISTRATIONS_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["timestamp", "name", "email", "phone", "payment_id", "webinar", "date"])
            writer.writeheader()
    return send_file(REGISTRATIONS_CSV, as_attachment=True, download_name="genai_masterclass_attendees.csv", mimetype="text/csv")


# ─── Health Check ──────────────────────────────────────────────────────────────
@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "webinar": WEBINAR_NAME,
        "date": WEBINAR_DATE,
        "host": HOST_NAME,
        "cohost": COHOST_NAME,
        "payments_enabled": ENABLE_PAYMENTS,
        "gateway": PAYMENT_GATEWAY if ENABLE_PAYMENTS else "NONE"
    }), 200


# ─── App Runner ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    print(f"""
+------------------------------------------------------+
|   [WEBINAR SERVER ACTIVE]
|   Webinar: {WEBINAR_NAME}
|   Schedule: {WEBINAR_DATE}
|   Hosts:   {HOST_NAME} & {COHOST_NAME} (Ex-InfoEdge)
+------------------------------------------------------+
|   Landing Page: http://localhost:{port}
|   Admin Portal: http://localhost:{port}/admin
|   Mode:         {'Live ' + PAYMENT_GATEWAY if ENABLE_PAYMENTS else 'Direct RSVP Mode (Ready for deployment)'}
+------------------------------------------------------+
    """)
    app.run(host="0.0.0.0", port=port, debug=debug)
