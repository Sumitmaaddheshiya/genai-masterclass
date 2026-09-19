# 🚀 GenAI Masterclass — Webinar Funnel & Registration Engine

A high-converting, production-ready webinar funnel and registration platform built for **Akash Mohan** and **Nikhil Mishra (Ex-InfoEdge)** for the live session on **Sunday, 27th September 2026 at 11:00 AM IST**.

---

## 🌟 Key Features

1. **High-Converting Landing Page (`index.html`)**:
   - Modern dark EdTech visual design with vibrant cyan/yellow accents and ambient glows.
   - Dynamic real-time urgency seat counter (decrements live).
   - Problem / Pain-point breakdown with social proof quotes.
   - 6 Core takeaway skills & live hands-on outcomes.
   - 2-Hour minute-by-minute live roadmap.
   - Verified instructor profiles featuring **Akash Mohan** (Funnel Architect) & **Nikhil Mishra** (GenAI Specialist, Ex-InfoEdge).
   - Interactive FAQ accordion & testimonial grid.
   - Instant celebration modal with 1-click **VIP WhatsApp Community** join button.
   - Ready-to-use **Google Ads & Meta Pixel** conversion tracking code hooks.

2. **Fullstack Backend Engine (`server.py`)**:
   - Serves landing page directly at `/` (zero 404 errors on cloud hosting).
   - Instant Attendee Registration API (`/register`) storing name, email, phone, and timestamps.
   - Double-buffered data persistence: `registrations.jsonl` (raw logs) and `registrations.csv` (spreadsheet ready).
   - Razorpay payment gateway integration ready (`/create-order` and `/webhook` HMAC verification) — toggleable with `ENABLE_PAYMENTS=true`.
   - Automated ticket email delivery with Zoom links (`send_confirmation_email`) — toggleable with `ENABLE_EMAILS=true`.

3. **Admin Portal & Attendee Export**:
   - Live Dashboard at `/admin` displaying total registrants, registration timestamps, and attendee cards.
   - 1-Click CSV Export at `/admin/export-csv` to easily load attendees into Excel, Google Sheets, or WhatsApp broadcast lists.

---

## ⚡ Quick Start (Local Run)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Server
```bash
python server.py
```

### 3. Open in Browser
- **Landing Page**: [http://localhost:5000](http://localhost:5000)
- **Admin Dashboard**: [http://localhost:5000/admin](http://localhost:5000/admin)
- **Direct CSV Download**: [http://localhost:5000/admin/export-csv](http://localhost:5000/admin/export-csv)

---

## 📂 Project Structure

```
Funnel/
├── index.html              # High-converting landing page & client logic
├── server.py               # Flask backend, registration API & admin dashboard
├── requirements.txt        # Production Python dependencies
├── .env                    # Environment configuration & toggle flags
├── .gitignore              # Protects secrets & private attendee records
├── poster.jpg              # High-resolution promotional graphic
├── registrations.csv       # Automatically generated attendee spreadsheet
├── registrations.jsonl     # Append-only raw attendee records
├── EXECUTION_PLAYBOOK.md   # 8-Phase master launch strategy & marketing scripts
└── README.md               # Documentation & quick start guide
```

---

## 💳 Activating Payments & Emails Later (When Ready)

When you receive your **Razorpay** keys or **Brevo/SMTP** credentials:

1. Open `.env`:
   ```env
   # Switch payments on
   ENABLE_PAYMENTS=true
   RAZORPAY_KEY_ID=rzp_live_your_actual_key
   RAZORPAY_KEY_SECRET=your_actual_secret
   RAZORPAY_WEBHOOK_SECRET=your_webhook_secret

   # Switch email dispatch on
   ENABLE_EMAILS=true
   SMTP_HOST=smtp-relay.brevo.com
   SMTP_PORT=587
   SMTP_USER=your_brevo_email
   SMTP_PASS=your_brevo_key
   ```
2. Restart `server.py`. The landing page will automatically switch from direct RSVP to the Razorpay checkout popup without changing any HTML!

---

## 🌐 Free 1-Click Cloud Deployment (Render.com)

1. Push this folder to a GitHub repository:
   ```bash
   git init
   git add .
   git commit -m "Initial launch of GenAI Masterclass Funnel"
   git branch -M main
   git remote add origin https://github.com/YOUR_USER/genai-funnel.git
   git push -u origin main
   ```
2. Go to [render.com](https://render.com) (Free Account):
   - Click **New +** → **Web Service**
   - Connect your GitHub repo.
   - Set:
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `gunicorn server:app` (or `python server.py`)
   - Add your `.env` variables in Render's Environment tab.
   - Click **Deploy**! Your page will be live on `https://your-app.onrender.com`.

---

## 🎯 Google Ads & Ad Campaigns

To run Google Ads with Nikhil:
1. Open `index.html`.
2. Uncomment the Google Tag Manager / Ads snippet inside `<head>`.
3. Paste your Google Ads Conversion ID (`AW-XXXXXXXXXX`).
4. Set daily budget on Google Ads (e.g., ₹200–₹500/day) targeting queries like:
   - *"learn generative ai workshop"*
   - *"practical chatgpt course india"*
   - *"hands on prompt engineering class"*
