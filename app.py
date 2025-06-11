from flask import Flask, request, jsonify
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
import openai
import os
import datetime

app = Flask(__name__)

# --- Config: API keys pre-filled ---
TWILIO_ACCOUNT_SID = "ACbd39e842a1d3cecc77d2bceb6bd39f24"
TWILIO_AUTH_TOKEN = "6f2bc7c8b8647647631b214774832bb5"
TWILIO_PHONE_NUMBER = "+18333823781"
OPENAI_API_KEY = "sk‑proj‑oKiIp6tIadmCST‑tCN4CtSwDzvXM8UWjwL1QTER2uPdX‑lEDt_PWUd7YtJYpkBGUxH1q1XbixoT3BlbkFJu_jUrJawGt_CMRDdJ2s5w3lQmnMKCCrvF--VE6Bownx8H‑3b‑D‑swm5uYgf2Km_C0tFX2g‑6sA"

# --- Clients ---
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
openai.api_key = OPENAI_API_KEY

# --- Trigger outbound call ---
@app.route("/make_call", methods=["POST"])
def make_call():
    data = request.json or {}
    to_number = data.get("to_number")
    if not to_number:
        return jsonify({"status":"error","message":"Missing to_number"}),400

    # Get webhook URL from env, with fallback
    webhook_url = os.environ.get("WEBHOOK_URL", "https://ai-caller-qej2.onrender.com") + "/voice"

    try:
        call = client.calls.create(
            to=to_number,
            from_=TWILIO_PHONE_NUMBER,
            url=webhook_url
        )
        msg = f"Placed call to {to_number}, SID: {call.sid}"
        log_line(msg)
        return jsonify({"status":"success","call_sid": call.sid})
    except Exception as e:
        log_line(f"Error placing call to {to_number}: {str(e)}")
        return jsonify({"status":"error","message":str(e)}),500

# --- Twilio voice webhook ---
@app.route("/voice", methods=["POST"])
def voice():
    resp = VoiceResponse()
    prompt = (
        "You are a professional real estate investor making a cold call to a seller. "
        "Speak confidently and persuasively. Your goal is to negotiate the lowest possible price "
        "to secure a wholesale deal. Be polite but firm."
    )
    ai_msg = get_ai_response(prompt)
    resp.say(ai_msg, voice="Polly.Matthew")
    resp.hangup()

    log_line(f"AI spoke: {ai_msg}")
    return str(resp)

# --- GPT helper ---
def get_ai_response(prompt):
    try:
        completion = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role":"system","content":"You are an expert real estate negotiator."},
                      {"role":"user","content":prompt}],
            max_tokens=200
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        log_line(f"Error generating AI response: {str(e)}")
        return "Sorry, there was an error generating the message."

# --- Logging ---
def log_line(text):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open("call_log.txt", "a") as f:
        f.write(f"[{timestamp}] {text}\n")

# --- Start server ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
