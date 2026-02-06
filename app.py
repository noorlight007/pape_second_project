from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response
from flask_session import Session
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
load_dotenv()
from typing import Any, Dict, Optional, Tuple
import httpx


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

def extract_message_fields(msg: Dict[str, Any]) -> Tuple[str, Optional[str], Optional[str], Optional[float], Optional[float]]:
    """
    Returns: (msg_type, text_body, media_id, latitude, longitude)
    """
    msg_type = msg.get("type")
    text_body = None
    media_id = None
    latitude = longitude = None

    if msg_type == "text":
        text_body = msg.get("text", {}).get("body")

    elif msg_type == "button":
        text_body = msg.get("button", {}).get("text")

    elif msg_type == "interactive":
        interactive = msg.get("interactive", {})
        if interactive.get("type") == "button_reply":
            text_body = interactive.get("button_reply", {}).get("title")
        elif interactive.get("type") == "list_reply":
            text_body = interactive.get("list_reply", {}).get("title")
        else:
            text_body = "[interactive]"

    elif msg_type == "image":
        text_body = "[image]"
        media_id = msg.get("image", {}).get("id")

    elif msg_type == "audio":
        text_body = "[audio]"

    elif msg_type == "document":
        text_body = "[document]"

    elif msg_type == "location":
        loc = msg.get("location", {})
        latitude = loc.get("latitude")
        longitude = loc.get("longitude")
        text_body = "[location]"

    else:
        text_body = f"[{msg_type or 'unknown'}]"

    return msg_type or "unknown", text_body, media_id, latitude, longitude

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

    url = f"https://graph.facebook.com/v23.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    try:
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})

                # Profile name (if present)
                profile_name = None
                try:
                    profile_name = value["contacts"][0]["profile"]["name"]
                    print(f"Profile name = {profile_name}")
                except Exception:
                    pass

                messages = value.get("messages")
                if not messages:
                    continue  # could be a status/event update

                msg = messages[0]
                msg_id = msg.get("id")

                # Duplicate guard
                if msg_id and msg_id in processed_message_ids:
                    print("🔁 Duplicate message. Skipping.")
                    return Response("ok", status=200, mimetype="text/plain")

                if msg_id:
                    processed_message_ids.add(msg_id)

                # Sender WhatsApp ID (phone number in international format without +)
                sender = msg.get("from")
                print(f"👤 Sender = {sender}")

                msg_type, text_body, media_id, latitude, longitude = extract_message_fields(msg)

                if media_id:
                    print(f"🖼️ media_id = {media_id}")
                if latitude is not None and longitude is not None:
                    print(f"📍 location = ({latitude}, {longitude})")

                print(f"💬 Message ({msg_type}) = {text_body}")

                # Build interactive reply
                text = f"👋 Bienvenue sur {profile_name or ''}!\nVotre assistant WhatsApp pour vous aider à trouver rapidement la bonne personne pour vos envois de colis ou vos trajets aéroportuaires, sans prise de tête.\nVeuillez sélectionner le service de votre choix :"
                footer_text = "Abra la lista del menú para elegir"

                payload = {
                    "messaging_product": "whatsapp",
                    "to": sender,
                    "type": "interactive",
                    "interactive": {
                        "type": "list",
                        "body": {"text": text.strip()},
                        "footer": {"text": footer_text},
                        "action": {
                            "button": "Todos los menús",
                            "sections": [
                                {
                                    "title": "Sélectionnez votre profil",
                                    "rows": [
                                        {
                                            "id": "role_driver",
                                            "title": "Envoyer un colis / document",
                                            
                                        },
                                        {
                                            "id": "role_customer",
                                            "title": "Être conduit à l’aéroport",
                                            
                                        },
                                        {
                                            "id": "role_driver",
                                            "title": "Être récupéré à l’aéroport",
                                            
                                        },
                                        {
                                            "id": "role_customer",
                                            "title": "Autres services",
                                            
                                        },
                                    ],
                                }
                            ]
                        },
                    },
                }

                # Send message to WhatsApp (sync httpx client for Flask route)
                with httpx.Client(timeout=20.0) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()

        return Response("ok", status=200, mimetype="text/plain")

    except httpx.HTTPStatusError as e:
        # Graph API returned non-2xx
        print("❌ WhatsApp API error:", e.response.text)
        return Response("WhatsApp API error", status=500, mimetype="text/plain")

    except Exception as e:
        print("❌ Error:", str(e))
        return Response("Server error", status=500, mimetype="text/plain")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)