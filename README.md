# GenAI Masterclass — Live Webinar Funnel & Registration Engine

A production-ready webinar funnel and registration platform built for **Akash Mohan** (Data Analyst at Pace Stock Broking Pvt Ltd) and **Nikhil Mishra** (GenAI Specialist, Ex-InfoEdge) for the live session on **Sunday, 27 September 2026 from 7:00 PM to 9:00 PM IST**.

---

## Key Features

1. **High-Converting Landing Page (`index.html`)**:
   - Modern, high-contrast aesthetic with Crisp White (`#ffffff`), Ink Slate (`#0f172a`), and Royal Blue (`#1d4ed8`) design tokens.
   - 100% emoji-free typography with minimalist glyphs (`•`, `✓`, `×`, `→`).
   - Dynamic real-time countdown timer targeting `Sunday, 27 September 2026 at 7:00 PM IST`.
   - "Reality Gap" contrast table comparing generic slide-based webinars to live terminal builds.
   - 6-step RAG architecture pipeline visualization.
   - 8 comprehensive curriculum modules mapping directly to industry workflows.
   - Verified instructor profiles for Akash Mohan and Nikhil Mishra.
   - Instant celebration modal providing direct 1-click Google Meet access and VIP WhatsApp community link.
   - Compliance navigation links in footer for payment gateway onboarding (`/terms`, `/privacy`, `/refund`, `/contact`).

2. **Fullstack Backend Engine (`server.py`)**:
   - Serves landing page directly at `/` (zero 404 errors on cloud hosting).
   - Instant attendee registration endpoint (`/register`) capturing name, email, and phone.
   - Dual-layer data persistence: `registrations.jsonl` (raw logs) and `registrations.csv` (spreadsheet ready).
   - Full PhonePe Payment Gateway integration (`/phonepe/pay`, `/phonepe/callback`, `/phonepe/webhook`).
   - Alternative Razorpay integration (`/create-order` and `/webhook` HMAC verification).
   - Dedicated PhonePe compliance pages (`/terms`, `/privacy`, `/refund`, `/contact`).
   - Automated attendee confirmation emails with Google Meet links (`send_confirmation_email`).

3. **Admin Portal & Attendee Export**:
   - Real-time attendee dashboard at `/admin` showing registrants, timestamps, and payment statuses.
   - 1-click CSV download at `/admin/export-csv` for spreadsheet analysis and WhatsApp outreach.

---

## Quick Start (Local Run)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Server
```bash
python server.py
```

### 3. Access in Browser
- **Landing Page**: [http://localhost:5000](http://localhost:5000)
- **Admin Dashboard**: [http://localhost:5000/admin](http://localhost:5000/admin)
- **Attendee CSV Export**: [http://localhost:5000/admin/export-csv](http://localhost:5000/admin/export-csv)

---

## Cloud Deployment (Render.com)

This repository includes `render.yaml` and `Procfile` for 1-click zero-configuration deployment on Render.com:

1. Push this repository to GitHub:
   ```bash
   git add .
   git commit -m "Finalize GenAI Masterclass funnel and PhonePe integration"
   git branch -M main
   git push -u origin main
   ```
2. Log in to [Render.com](https://render.com) (free account).
3. Click **New +** -> **Web Service**.
4. Select your GitHub repository: `https://github.com/aka-ish/genai-masterclass`.
5. Render automatically recognizes the configuration:
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn server:app`
6. Click **Deploy Web Service**.
7. Once deployed, your public URL will look like: `https://genai-masterclass.onrender.com`.

---

## PhonePe Payment Gateway Onboarding

When setting up PhonePe Payment Gateway:

1. **Submit Deployed URL**:
   Provide your live Render URL (`https://genai-masterclass.onrender.com`) to the PhonePe merchant portal (`business.phonepe.com`). PhonePe compliance requires active legal links:
   - Terms & Conditions: `https://genai-masterclass.onrender.com/terms`
   - Privacy Policy: `https://genai-masterclass.onrender.com/privacy`
   - Cancellation & Refund Policy: `https://genai-masterclass.onrender.com/refund`
   - Contact Us: `https://genai-masterclass.onrender.com/contact`

2. **Sandbox Testing**:
   By default, sandbox testing is supported using the default preprod credentials:
   - Merchant ID: `PGTESTPAYUAT`
   - Salt Key: `099eb0cd-02cf-4e2a-8aca-3e6c6aff0399`
   - Salt Index: `1`

3. **Switch to Live Production**:
   Once PhonePe activates your production Merchant ID and Salt Key, update your environment variables in Render:
   ```env
   ENABLE_PAYMENTS=true
   PAYMENT_GATEWAY=PHONEPE
   PHONEPE_ENV=PROD
   PHONEPE_MERCHANT_ID=your_production_merchant_id
   PHONEPE_SALT_KEY=your_production_salt_key
   PHONEPE_SALT_INDEX=1
   WEBINAR_PRICE_INR=49
   ```
