# AI Caller App

## Setup

1. **Upload all files** (`app.py`, `requirements.txt`, `render.yaml`, `README.md`) to your GitHub repo.

2. **Deploy on Render**
   - In Render dashboard, create a new Web Service using this repo.
   - **Start Command**: `python app.py`
   - **Environment variables**: `WEBHOOK_URL` will be automatically set to your Render URL.

3. **Configure Twilio webhook**
   - In Twilio Console > Phone Numbers > (your number) > Voice & Fax:
     - **Request URL (CALLS)**: `{{WEBHOOK_URL}}/voice`

4. **Trigger an outbound call:**

```bash
curl -X POST https://<your-render-url>/make_call \
  -H "Content-Type: application/json" \
  -d '{"to_number":"+1TARGET_NUMBER"}'
