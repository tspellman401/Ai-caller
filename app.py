from flask import Flask, request, jsonify
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
import openai
import os
import datetime

app = Flask(__name__)

# --- Config: API keys ---
TWILIO_ACCOUNT_SID = "ACbd39e842a1d3cecc77d2bceb6bd39f24"
TWILIO_AUTH_TOK ='6f2bc7c8b8647647631b214774832bb5"
TWILIO_PHONE_NUMBER = "+18333823781"
OPENAI_API_KEY = "sk‑proj‑oKiIp6tIadmCST‑tCN4CtSwDzvXM8UWjwL1QTER2uPdX‑lEDt_PWUd7YtJYpkBGUxH1q1XbixoT3BlbkFJu_jUrJawGt_CMRDdJ2s5w3lQmnMKCCrvF--VE6Bownx8H‑3b‑D‑swm5uYgf2Km_C0tFX2g‑6sA"

# --- Clients ---
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
openai.api_key = OPENAI_API_KEY

# --- Trigger outbound 
@app.route("/make_call", methods=["POST"])
def make_call():
    data = request.json or {}
    to_number = data.get("to_number")
    if not to_number:
        return jsonify({"status":"error","message":"Missing to_number"}),400

    # Get webhook URL with fallback
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
        # Improved 401 logging
        if "Authenticate" in str(e) or "401" in str(e):
            log_line("ERROR: Twilio 401 Unauthorized - check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN (likely wrong or test credentials)")
        else:
            log_line(f"Error placing call to {to_number}: {str(e)}")
        return jsonify({"status":"error","message":str(e)}),500

    # Get webhook URL with fallback
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

    gather = resp.gather(
        input='speech',
        timeout=5,
        speechTimeout='auto',
        action='/gather',
        method='POST'
    )

    # First pro negotiation message
    first_prompt = (
        "Hi, this is Tom, a local real estate investor. "
        "I wanted to see if you'd consider a quick cash offer on your property. "
        "Can you tell me a little about your situation with the property?"
    )

    gather.say(first_prompt, voice="Polly.Matthew")
    resp.redirect('/voice')  # Loop back if no input

    log_line(f"AI first prompt: {first_prompt}")
    return str(resp)

# --- Twilio gather response ---
@app.route("/gather", methods=["POST"])
def gather():
    resp = VoiceResponse()
    speech_result = request.form.get('SpeechResult', '')

    # Pro follow-up negotiation prompt
    follow_up_prompt = (
        f"You are a professional real estate investor on a phone call. "
        f"The seller just said: '{speech_result}'. "
        "Respond in a friendly and persuasive way. "
        "Ask about the property, their timeline to sell, and any flexibility on price."
    )

    ai_reply = get_ai_response(follow_up_prompt)

    gather = resp.gather(
        input='speech',
        timeout=5,
        speechTimeout='auto',
        action='/gather',
        method='POST'
    )
    gather.say(ai_reply, voice="Polly.Matthew")

    log_line(f"Seller said: {speech_result} | AI reply: {ai_reply}")
    return str(resp)

# --- GPT helper ---
def get_ai_response(prompt):
    try:
        completion = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role":"system","content":(
                "You are an expert real estate negotiator on a phone call. "
                "Your goal is to build rapport, uncover seller motivation, understand property condition, "
                "and negotiate a great price for a wholesale deal. Speak naturally and confidently."
            )},
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
