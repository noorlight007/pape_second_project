from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response
from datetime import datetime, timedelta
import os, json
from dotenv import load_dotenv
load_dotenv()
from typing import Any, Dict, Optional, Tuple
import httpx
import logging
logging.basicConfig(level=logging.INFO)

from tasks import process_webhook

app = Flask(__name__)
app.config['secret_key'] = '5800d5d9e4405020d527f0587538abbe'


WHATSAPP_PHONE_NUMBER_ID=os.getenv("PHONE_NUMBER_ID")
WHATSAPP_ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
VERIFY_TOKEN = "6984125oO!?"


# ==================== FLASK ROUTES ====================

@app.get("/")
def test():
    return render_template("index.html")

@app.get("/privacy-policy")
def privacy_policy():
    return render_template("privacy_policy.html")

@app.get("/terms-of-service")
def terms_of_service():
    return render_template("terms_of_service.html")

def is_inbound_message_event(data: dict) -> bool:
    value = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
    if 'statuses' in value:
        return False
    return True

@app.get("/webhookone")
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    app.logger.info("VERIFY hit mode=%s token_ok=%s", mode, token == VERIFY_TOKEN)
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200

    return "Forbidden", 403


@app.post("/webhookone")
def receive():
    app.logger.info("POST /webhookone hit. headers=%s", dict(request.headers))
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    print(data)

    try:
        

        if not is_inbound_message_event(data):
            app.logger.info("Not a valid message", dict(request.headers))
            return "ok", 200
        process_webhook.delay(data)  # Process the webhook asynchronously with Celery
        return "okay", 200
    except Exception as e:
        print(str(e))
        return "okay", 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)