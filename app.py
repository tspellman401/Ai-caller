from flask import Flask, request, jsonify, session
from flask_cors import CORS
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
import openai
import os
import datetime
import time

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Needed for session tracking (loop count)

# Enable CORS for all routes
CORS(app)

# --- Config: API keys ---
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
        if "Authenticate" in str(e) or "401" in str(e):
            log_line("ERROR: Twilio 401 Unauthorized - check TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN (likely wrong or test credentials)")
        else:
            log_line(f"Error placing call to {to_number}: {str(e)}")
        return jsonify({"status":"error","message":str(e)}),500

# --- Twilio voice webhook ---
@app.route("/voice", methods=["POST"])
def voice():
    session["loop_count"] = 0  # Reset loop count at start of call
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

    # Safely get seller speech result
    speech_result = request.form.get('SpeechResult', '')
    if not speech_result:
        speech_result = ''
    log_line(f"Raw SpeechResult: {speech_result}")

    # Exit logic → if seller says "not interested", AI will thank and hang up
    exit_phrases = ["not interested", "no thank you", "stop calling", "do not call", "not selling", "not for sale"]

    if any(phrase in speech_result.lower() for phrase in exit_phrases):
        resp.say("Understood. Thank you for your time. Have a great day!")
        resp.hangup()
        log_line(f"Seller said: {speech_result} | AI ending call politely.")
        return str(resp)

    # Loop count limit → prevent infinite loop
    try:
        loop_count = session.get("loop_count", 0) + 1
        session["loop_count"] = loop_count
    except Exception as e:
        log_line(f"Session error: {str(e)} → using fallback loop_count = 1")
        loop_count = 1

    if loop_count >= 5:
        resp.say("Thank you again for your time. Goodbye.")
        resp.hangup()
        log_line(f"Max loop reached ({loop_count}), ending call.")
        return str(resp)

    # Pro follow-up negotiation prompt
    follow_up_prompt = (
        f"You are a professional real estate investor on a phone call. "
        f"The seller just said: '{speech_result}'. "
        "Respond in a friendly and persuasive way. "
        "Follow this flow: "
        "1. Build rapport, 2. Understand motivation, 3. Ask about property condition, "
        "4. Ask about timeline to sell, 5. Ask about flexibility on price, 6. If motivated, pitch cash offer, "
        "7. If not motivated or says not interested, exit call politely."
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

    log_line(f"Loop {loop_count} | Seller said: {speech_result} | AI reply: {ai_reply}")
    return str(resp)

# --- GPT helper with retry ---
def get_ai_response(prompt, max_retries=3, retry_delay=2):
    attempt = 0
    while attempt < max_retries:
        try:
            completion = openai.ChatCompletion.create(
                model="gpt-4o",
                messages=[{"role":"system","content":(
                    "You are an expert real estate negotiator on a phone call. "
                    "Your goal is to build rapport, uncover seller motivation, understand property condition, "
                    "and negotiate a great price for a wholesale deal. Speak naturally and confidently. "
                    "Follow this flow strictly: 1. Build rapport, 2. Understand motivation, 3. Property condition, "
                    "4. Timeline to sell, 5. Flexibility on price, 6. If motivated, pitch cash offer, "
                    "7. If not motivated or says not interested, exit call politely."
                )},
                {"role":"user","content":prompt}],
                max_tokens=200
            )
            ai_message = completion.choices[0].message.content.strip()
            if not ai_message:
                log_line("Warning: GPT returned empty message → using fallback polite message.")
                return "Thank you for sharing. Could you tell me more about your property?"
            return ai_message
        except Exception as e:
            attempt += 1
            log_line(f"GPT error on attempt {attempt}: {str(e)}")
            if attempt < max_retries:
                log_line(f"Retrying GPT in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                log_line("Max GPT retry attempts reached. Using fallback polite message.")
                return "Sorry, I didn't quite catch that. Could you tell me more about your property?"

# --- Logging ---
def log_line(text):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {text}"
    print(log_entry)  # Also log to Render Logs
    with open("call_log.txt", "a") as f:
        f.write(log_entry + "\n")

# --- Start server ---
if __name__ == "__main__":
    print(f"Using TWILIO_ACCOUNT_SID: {TWILIO_ACCOUNT_SID}")
    print(f"Using TWILIO_PHONE_NUMBER: {TWILIO_PHONE_NUMBER}")
    print(f"Using WEBHOOK_URL: {os.environ.get('WEBHOOK_URL', 'https://ai-caller-qej2.onrender.com') + '/voice'}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
