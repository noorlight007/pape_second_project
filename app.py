from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response
from flask_session import Session
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
load_dotenv()
from typing import Any, Dict


app = Flask(__name__)
app.config['secret_key'] = '5800d5d9e4405020d527f0587538abbe'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=60)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

WHATSAPP_PHONE_NUMBER_ID=os.getenv("PHONE_NUMBER_ID")
WHATSAPP_ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
VERIFY_TOKEN = "6984125oO!"

processed_message_ids = set()

@app.get("/")
def test():
    return {"okay": True}

@app.get("/webhook")
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return Response(challenge, status=200, mimetype="text/plain")

    return Response("Unauthorized", status=403, mimetype="text/plain")


@app.post("/webhook")
def receive():
    data: Dict[str, Any] = request.get_json(silent=True) or {}
    print("📩 Incoming message:", data)
    return Response("OK", status=200, mimetype="text/plain")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)