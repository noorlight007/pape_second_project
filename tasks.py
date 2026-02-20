from celery_app import celery
from typing import Any, Dict, Optional, Tuple
import httpx
from whatsapp_http import send_whatsapp_message

import os, json
from dotenv import load_dotenv
load_dotenv()

WHATSAPP_PHONE_NUMBER_ID=os.getenv("PHONE_NUMBER_ID")
WHATSAPP_ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
WHATSAPP_PERMANENT_TOKEN = os.getenv("PARMANENT_ACCESS_TOKEN")
VERIFY_TOKEN = "6984125oO!?"


from location_manage import get_countries, get_cities_by_country
from message_ids import add_message_id
from utils import *

import redis
r = redis.Redis(host="localhost", port=6379, decode_responses=True)


def state_key(sender): 
    return f"wa:state:{sender}"

def data_key(sender):
    return f"wa:data:{sender}"

def error_count_key(sender):
    return f"wa:error_count:{sender}"

def get_state(sender):
    return r.get(state_key(sender))

def set_state(sender, state):
    r.setex(state_key(sender), 60*60, state)  # 60 minutes TTL

def clear_state(sender) -> bool:
    return r.delete(state_key(sender)) == 1

# ----------- Parcel request data management in Redis (can be used to store intermediate data during the conversation) -----------
def get_data(sender) -> dict:
    """Get stored conversation data for a user"""
    data = r.get(data_key(sender))
    if data:
        return json.loads(data)
    return {}

def set_data(sender, data: dict):
    """Store conversation data for a user"""
    r.setex(data_key(sender), 60*60, json.dumps(data))  # 60 minutes TTL

def update_data(sender, key: str, value: any):
    """Update a specific field in user's conversation data"""
    data = get_data(sender)
    data[key] = value
    set_data(sender, data)

def clear_data(sender) -> bool:
    """Clear all stored data for a user"""
    return r.delete(data_key(sender)) == 1


# ----------- Error counts -----------
def get_error_count_exceeds_3(sender) -> int:
    """Get error count for a user"""
    count = r.get(error_count_key(sender))
    if int(count) >= 3:
        return True
    return False

def increment_error_count(sender):
    """Increment error count for a user"""
    r.incr(error_count_key(sender))

def clear_error_count(sender):
    """Clear error count for a user"""
    r.delete(error_count_key(sender))


def clear_all(sender):
    """Clear both state and data for a user"""
    clear_state(sender)
    clear_data(sender)

# ---- END of Redis data management functions for conversation state and data ----



# ==================== HELPER FUNCTIONS ====================

def build_summary(sender: str) -> str:
    """Build a formatted summary of the user's shipment request"""
    data = get_data(sender)
    
    summary = "📝 Merci pour ces informations !\n\nVoici le récapitulatif de votre demande :\n"
    
    # Departure information
    if data.get('departure_country') and data.get('departure_city'):
        summary += f"📍 *Départ:*\n"
        summary += f"   Pays: {data['departure_country']}\n"
        summary += f"   Ville: {data['departure_city']}\n"
    
    # Destination information
    if data.get('destination_country') and data.get('destination_city'):
        summary += f"🎯 *Destination:*\n"
        summary += f"   Pays: {data['destination_country']}\n"
        summary += f"   Ville: {data['destination_city']}\n"
    
    # Send date
    if data.get('send_date'):
        summary += f"📅 *Date d'envoi:* {data['send_date']}\n"
    
    # Shipping type
    if data.get('shipping_type'):
        summary += f"📦 *Type d'envoi:* {data['shipping_type']}\n\nVeuillez confirmer la demande :"
    
    return summary

def send_whatsapp_message(sender: str, payload: dict, headers: dict, url: str):
    """Helper function to send WhatsApp messages"""
    with httpx.Client(timeout=20.0) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp




@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def process_webhook(self, payload: dict):
    """
    Do slow work here: DB writes, API calls, business logic
    """
    # print(payload)
    # your processing logic
    data = payload

    
    url = f"https://graph.facebook.com/v23.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_PERMANENT_TOKEN}",
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
                print(msg)
                msg_id = msg.get("id")

                new_msg_check = add_message_id(msg_id)
                if not new_msg_check:
                    print("🔁 Duplicate message. Skipping.")
                    return "okay", 200


                # Duplicate guard
                # if msg_id and msg_id in processed_message_ids:
                #     print("🔁 Duplicate message. Skipping.")
                #     return "okay", 200

                # if msg_id:
                #     processed_message_ids.add(msg_id)

                

                # Sender WhatsApp ID (phone number in international format without +)
                sender = msg.get("from")
                print(f"👤 Sender = {sender}")

                msg_type, list_msg_id, button_msg_id, text_body, media_id, latitude, longitude = extract_message_fields(msg)

                if media_id:
                    print(f"🖼️ media_id = {media_id}")
                if latitude is not None and longitude is not None:
                    print(f"📍 location = ({latitude}, {longitude})")

                print(f"💬 Message ({msg_type}) = {text_body}")
                # session['msg_context'][sender]['state']
                print(f"📊 Current session context: {get_state(sender) if get_state(sender) else 'None'}")

                if not get_state(sender):
                    # Build interactive reply
                    text = f"👋 Bienvenue sur e-service {profile_name or ''} !\n\nVotre assistant WhatsApp pour vous aider à trouver rapidement la bonne personne pour vos envois de colis ou vos trajets aéroportuaires, sans prise de tête.\n\nVeuillez Choisir le service de votre choix :"
                    # footer_text = "Veuillez Choisir le service de votre choix :"

                    payload = {
                        "messaging_product": "whatsapp",
                        "to": sender,
                        "type": "interactive",
                        "interactive": {
                            "type": "list",
                            "body": {"text": text.strip()},
                            # "footer": {"text": footer_text},
                            "action": {
                                "button": "Afficher le menu",
                                "sections": [
                                    {
                                        "title": "Seleccione desde aquí",
                                        "rows": [
                                            {
                                            "id": "role_driver1",
                                            "title": "Envoyer un colis"
                                            },
                                            {
                                            "id": "role_customer2",
                                            "title": "Aller à l’aéroport"
                                            },
                                            {
                                            "id": "role_driver3",
                                            "title": "Retour de l’aéroport"
                                            },
                                            {
                                            "id": "role_customer4",
                                            "title": "Autres services"
                                            }

                                        ],
                                    }
                                ]
                            },
                        },
                    }

                    # Update state for next step
                    set_state(sender, "service_selected")

                    # Send message to WhatsApp (sync httpx client for Flask route)
                    send_whatsapp_message(sender, payload, headers, url)
                    

                    return "ok", 200
                
                # New flow: user has selected a service from the menu
                elif get_state(sender) == "service_selected":
                    ## Continue here
                    if msg_type == "interactive_list_reply" and list_msg_id == "role_driver1":
                        # resetting error count on valid selection
                        clear_error_count(sender)

                        # Store service type
                        update_data(sender, 'service_type', 'Envoyer un colis')

                        countries = get_countries()
                        text = "🙏 Super, merci pour votre choix !\n🌍 Dans quel pays se trouve le colis / document ?"
                        rows = []
                        for c in countries:
                            rows.append({
                                "id": f"list_country_{c['id']}",
                                "title": c['name']
                            })
                        payload = {
                            "messaging_product": "whatsapp",
                            "to": sender,
                            "type": "interactive",
                            "interactive": {
                                "type": "list",
                                "body": {"text": text.strip()},
                                "action": {
                                    "button": "Choisir le pays",
                                    "sections": [
                                        {
                                            "title": "Pays",
                                            "rows": rows
                                        }
                                    ]
                                },
                            },
                        }

                        set_state(sender, "shipment_country_selected")
                        # Send message to WhatsApp (sync httpx client for Flask route)
                        send_whatsapp_message(sender, payload, headers, url)
                        return "ok", 200

                    elif msg_type == "interactive_list_reply" and list_msg_id in ["role_customer2", "role_driver3", "role_customer4"]:
                        text = f"✅ Service: {text_body}\n\n(Flow à implémenter...)"
                        payload = {
                            "messaging_product": "whatsapp",
                            "to": sender,
                            "type": "text",
                            "text": {"body": text.strip()}
                        }
                        send_whatsapp_message(sender, payload, headers, url)
                        return "okay", 200

                    else:
                        text = "❌ Oups, cette opération n’est pas disponible.\nVeuillez Choisir une option valide parmi celles proposées."
                        payload = {
                            "messaging_product": "whatsapp",
                            "to": sender,
                            "type": "text",
                            "text": {
                                "body": text.strip()
                            }
                        }
                        
                        # Send message to WhatsApp (sync httpx client for Flask route)
                        send_whatsapp_message(sender, payload, headers, url)
                        # clear_state(sender)
                        # clear_data(sender)
                        print("⚠️ Unexpected message type or list selection in service selection step.")
                        increment_error_count(sender)
                        if get_error_count_exceeds_3(sender):
                            clear_all(sender)
                            clear_error_count(sender)
                            print("⚠️ Too many errors. Resetting conversation.")
                        return "ok", 200

                elif get_state(sender) == "shipment_country_selected":
                    if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_country_"):
                        # resetting error count on valid selection
                        clear_error_count(sender)

                        country_id = list_msg_id.replace("list_country_", "")
                        # Store departure country
                        country = text_body
                        if country:
                            update_data(sender, 'departure_country_id', country_id)
                            update_data(sender, 'departure_country', country)
                        
                        cities = get_cities_by_country(country_id)
                        text = "📍 Dans quelle ville se trouve le colis / document ?"
                        rows = []
                        for c in cities:
                            rows.append({
                                "id": f"list_city_{c['id']}",
                                "title": c['name']
                            })
                        payload = {
                            "messaging_product": "whatsapp",
                            "to": sender,
                            "type": "interactive",
                            "interactive": {
                                "type": "list",
                                "body": {"text": text.strip()},
                                "action": {
                                    "button": "Choisir la ville",
                                    "sections": [
                                        {
                                            "title": "Villes",
                                            "rows": rows
                                        }
                                    ]
                                },
                            },
                        }
                        set_state(sender, "departure_city_selected")
                        # Send message to WhatsApp (sync httpx client for Flask route)
                        send_whatsapp_message(sender, payload, headers, url)
                        return "ok", 200
                    
                    else:
                        text = "❌ Oups, cette opération n’est pas disponible.\nVeuillez Choisir une option valide parmi celles proposées."
                        payload = {
                            "messaging_product": "whatsapp",
                            "to": sender,
                            "type": "text",
                            "text": {
                                "body": text.strip()
                            }
                        }
                        # Send message to WhatsApp (sync httpx client for Flask route)
                        # clear_state(sender)
                        # clear_data(sender)
                        send_whatsapp_message(sender, payload, headers, url)
                        increment_error_count(sender)
                        if get_error_count_exceeds_3(sender):
                            clear_all(sender)
                            clear_error_count(sender)
                            print("⚠️ Too many errors. Resetting conversation.")
                        print("⚠️ Unexpected message type or list selection in country selection step.")
                        return "ok", 200

                elif get_state(sender) == "departure_city_selected":
                    if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_city_"):
                        # resetting error count on valid selection
                        clear_error_count(sender)

                        city_id = list_msg_id.replace("list_city_", "")

                        # Store departure city
                        city = text_body
                        if city:
                            update_data(sender, 'departure_city_id', city_id)
                            update_data(sender, 'departure_city', city)
                        
                        countries = get_countries()
                        rows = []
                        for c in countries:
                            rows.append({
                                "id": f"list_country_{c['id']}",
                                "title": c['name']
                            })
                        text = f"🌍 Dans quel pays allez-vous envoyer le colis / document ?"
                        payload = {
                            "messaging_product": "whatsapp",
                            "to": sender,
                            "type": "interactive",
                            "interactive": {
                                "type": "list",
                                "body": {"text": text.strip()},
                                "action": {
                                    "button": "Choisir le pays",
                                    "sections": [
                                        {
                                            "title": "Pays",
                                            "rows": rows
                                        }
                                    ]
                                },
                            },
                        }

                        set_state(sender, "destination_country_selected")
                        # Send message to WhatsApp (sync httpx client for Flask route)
                        send_whatsapp_message(sender, payload, headers, url)
                        return "ok", 200
                    else:
                        text = "❌ Oups, cette opération n’est pas disponible.\nVeuillez Choisir une option valide parmi celles proposées."
                        payload = {
                            "messaging_product": "whatsapp",
                            "to": sender,
                            "type": "text",
                            "text": {
                                "body": text.strip()
                            }
                        }
                        # Send message to WhatsApp (sync httpx client for Flask route)
                        send_whatsapp_message(sender, payload, headers, url)

                        increment_error_count(sender)
                        if get_error_count_exceeds_3(sender):
                            clear_all(sender)
                            clear_error_count(sender)
                            print("⚠️ Too many errors. Resetting conversation.")

                        print("⚠️ Unexpected message type or list selection in city selection step.")
                        return "ok", 200

                elif get_state(sender) == "destination_country_selected":
                    if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_country_"):
                        # resetting error count on valid selection
                        clear_error_count(sender)

                        country_id = list_msg_id.replace("list_country_", "")

                        # Store destination country
                        country = text_body
                        if country:
                            update_data(sender, 'destination_country_id', country_id)
                            update_data(sender, 'destination_country', country)

                        cities = get_cities_by_country(country_id)
                        rows = []
                        for c in cities:
                            rows.append({
                                "id": f"list_city_{c['id']}",
                                "title": c['name']
                            })
                        text = f"📍 Dans quelle ville allez-vous envoyer le colis / document ?"
                        payload = {
                            "messaging_product": "whatsapp",
                            "to": sender,
                            "type": "interactive",
                            "interactive": {
                                "type": "list",
                                "body": {"text": text.strip()},
                                "action": {
                                    "button": "Choisir la ville",
                                    "sections": [
                                        {
                                            "title": "Villes",
                                            "rows": rows
                                        }
                                    ]
                                },
                            },
                        }

                        set_state(sender, "destination_city_selected")
                        # Send message to WhatsApp (sync httpx client for Flask route)
                        send_whatsapp_message(sender, payload, headers, url)
                        return "ok", 200
                    
                    else:
                        text = "❌ Oups, cette opération n’est pas disponible.\nVeuillez Choisir une option valide parmi celles proposées."
                        payload = {
                            "messaging_product": "whatsapp",
                            "to": sender,
                            "type": "text",
                            "text": {
                                "body": text.strip()
                            }
                        }
                        # Send message to WhatsApp (sync httpx client for Flask route)
                        send_whatsapp_message(sender, payload, headers, url)

                        increment_error_count(sender)
                        if get_error_count_exceeds_3(sender):
                            clear_all(sender)
                            clear_error_count(sender)
                            print("⚠️ Too many errors. Resetting conversation.")

                        print("⚠️ Unexpected message type or list selection in destination country selection step.")
                        return "ok", 200
                
                elif get_state(sender) in ["destination_city_selected"]:
                    if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("list_city_"):
                        # resetting error count on valid selection
                        clear_error_count(sender)

                        city_id = list_msg_id.split("_")[-1]

                        # Store destination city
                        city = text_body
                        if city:
                            update_data(sender, 'destination_city_id', city_id)
                            update_data(sender, 'destination_city', city)
                        
                        text = "📅 Quand souhaitez-vous envoyer votre colis / document ?"
                        payload = {
                            "messaging_product": "whatsapp",
                            "to": sender,
                            "type": "interactive",
                            "interactive": {
                                "type": "list",
                                "body": {"text": text.strip()},
                                "action": {
                                    "button": "Choisir la date",
                                    "sections": [
                                        {
                                            "title": "Date d'envoi",
                                            "rows": [
                                                {
                                                    "id": "send_date_72h",
                                                    "title": "Dans moins de 72 heures"
                                                },
                                                {
                                                    "id": "send_date_this_week",
                                                    "title": "Cette semaine"
                                                },
                                                {
                                                    "id": "send_date_next_week",
                                                    "title": "La semaine prochaine"
                                                },
                                                {
                                                    "id": "send_date_other",
                                                    "title": "Une date ultérieure"
                                                }
                                            ]
                                        }
                                    ]
                                },
                            },
                        }
                        set_state(sender, "send_date_selected")
                        # Send message to WhatsApp (sync httpx client for Flask route)
                        send_whatsapp_message(sender, payload, headers, url)
                        return "ok", 200

                    else:
                        text = "❌ Oups, cette opération n’est pas disponible.\nVeuillez Choisir une option valide parmi celles proposées."
                        payload = {
                            "messaging_product": "whatsapp",
                            "to": sender,
                            "type": "text",
                            "text": {
                                "body": text.strip()
                            }
                        }
                        # Send message to WhatsApp (sync httpx client for Flask route)
                        send_whatsapp_message(sender, payload, headers, url)

                        increment_error_count(sender)
                        if get_error_count_exceeds_3(sender):
                            clear_all(sender)
                            clear_error_count(sender)
                            print("⚠️ Too many errors. Resetting conversation.")
                            
                        print("⚠️ Unexpected message type or list selection in destination city selection step.")
                        return "ok", 200

                elif get_state(sender) == "send_date_selected":
                    if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("send_date_"):
                        # resetting error count on valid selection
                        clear_error_count(sender)

                        send_date_option = list_msg_id.replace("send_date_", "")

                        # Store send date
                        update_data(sender, 'send_date', text_body)
                        # Here you would typically save the collected info to your database and/or proceed with the next steps of your flow
                        text = f"📦 Quel est le type d'envoi ?"

                        # List of shipping types - you can replace with actual types from your database
                        
                        shipping_types = [
                            {"id": "shipping_type_Petits colis", "title": "Petits colis"},
                            {"id": "shipping_type_Moyens colis", "title": "Moyens colis"},
                            {"id": "shipping_type_Mixte petits/moyens", "title": "Mixte petits/moyens"},
                            {"id": "shipping_type_Grands colis", "title": "Grands colis"},
                            {"id": "shipping_type_Documents", "title": "Documents"},
                            {"id": "shipping_type_Petites valises", "title": "Petites valises"},
                            {"id": "shipping_type_Moyennes valises", "title": "Moyennes valises"},
                            {"id": "shipping_type_Mixte ptes/moyennes", "title": "Mixte ptes/moyennes"},
                            {"id": "shipping_type_Grandes valises", "title": "Grandes valises"},
                            {"id": "shipping_type_Mixte colis/docs/bagages", "title": "Mixte colis/docs/bagages"},
                        ]

                        payload = {
                            "messaging_product": "whatsapp",
                            "to": sender,
                            "type": "interactive",
                            "interactive": {
                                "type": "list",
                                "body": {
                                    "text": text.strip()
                                },
                                "action": {
                                    "button": "Choix type colis ?",
                                    "sections": [
                                        {
                                            "title": "Types d'envoi",
                                            "rows": shipping_types
                                        }
                                    ]
                                }
                            }
                        }

                        set_state(sender, "shipping_type_selected")

                        # Send message to WhatsApp (sync httpx client for Flask route)
                        send_whatsapp_message(sender, payload, headers, url)
                        return "ok", 200
                    else:
                        text = "❌ Oups, cette opération n’est pas disponible.\nVeuillez Choisir une option valide parmi celles proposées."
                        payload = {
                            "messaging_product": "whatsapp",
                            "to": sender,
                            "type": "text",
                            "text": {
                                "body": text.strip()
                            }
                        }
                        # Send message to WhatsApp (sync httpx client for Flask route)
                        send_whatsapp_message(sender, payload, headers, url)

                        increment_error_count(sender)
                        if get_error_count_exceeds_3(sender):
                            clear_all(sender)
                            clear_error_count(sender)
                            print("⚠️ Too many errors. Resetting conversation.")

                        print("⚠️ Unexpected message type or list selection in send date selection step.")
                        return "ok", 200

                elif get_state(sender) == "shipping_type_selected":
                    if msg_type == "interactive_list_reply" and list_msg_id and list_msg_id.startswith("shipping_type_"):
                        # resetting error count on valid selection
                        clear_error_count(sender)

                        shipping_type_id = list_msg_id.replace("shipping_type_", "")
                        # Store shipping type
                        update_data(sender, 'shipping_type', text_body)

                        # Here you would typically save the collected info to your database and/or proceed with the next steps of your flow
                        # Build and send summary
                        text = build_summary(sender)
                        ## You can build a nice summary of the collected info here to show to the user before confirming the request
                        payload = {
                            "messaging_product": "whatsapp",
                            "to": sender,
                            "type": "interactive",
                            "interactive": {
                                "type": "button",
                                "body": {
                                    "text": text.strip()
                                },
                                "action": {
                                    "buttons": [
                                        {
                                            "type": "reply",
                                            "reply": {
                                                "id": "parcel_req_Oui",
                                                "title": "Oui"
                                            }
                                        },
                                        {
                                            "type": "reply",
                                            "reply": {
                                                "id": "parcel_req_Non",
                                                "title": "Non"
                                            }
                                        }
                                    ]
                                }
                            }
                        }
                        
                        # Send message to WhatsApp (sync httpx client for Flask route)
                        send_whatsapp_message(sender, payload, headers, url)
                        
                        set_state(sender, "request_confirmation")
                        
                        return "ok", 200
                    else:
                        text = "❌ Oups, cette opération n'est pas disponible.\nVeuillez Choisir une option valide parmi celles proposées."
                        payload = {
                            "messaging_product": "whatsapp",
                            "to": sender,
                            "type": "text",
                            "text": {
                                "body": text.strip()
                            }
                        }
                        # Send message to WhatsApp (sync httpx client for Flask route)
                        send_whatsapp_message(sender, payload, headers, url)

                        increment_error_count(sender)
                        if get_error_count_exceeds_3(sender):
                            clear_all(sender)
                            clear_error_count(sender)
                            print("⚠️ Too many errors. Resetting conversation.")

                        print("⚠️ Unexpected message type or list selection in shipping type selection step.")
                        return "ok", 200
                
                elif get_state(sender) == "request_confirmation":
                    if msg_type == "interactive_button_reply" and button_msg_id in ["parcel_req_Oui", "parcel_req_Non"]:
                        # resetting error count on valid selection
                        clear_error_count(sender)

                        if button_msg_id == "parcel_req_Oui":
                            text = "🔍 Votre demande est bien enregistrée.\nNous lançons immédiatement la recherche d’un GP disponible correspondant à vos critères.\n\n⏳ Merci de patienter quelques instants…\n\n⚠️ Attention, au-delà de 15 min d'attente, veuillez considérer que nous n'avons pas pu satisfaire votre demande et nous vous recommandons de refaire une autre demande ultérieurement."
                            # Here you would typically save the confirmed request to your database and/or trigger the next steps of your flow
                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "text",
                                "text": {
                                    "body": text.strip()
                                }
                            }
                            send_whatsapp_message(sender, payload, headers, url)

                            clear_state(sender)
                            clear_data(sender)
                            return "ok", 200

                        elif button_msg_id == "parcel_req_Non":
                            # Build interactive reply
                            text = f"Votre assistant WhatsApp pour vous aider à trouver rapidement la bonne personne pour vos envois de colis ou vos trajets aéroportuaires, sans prise de tête.\n\nVeuillez Choisir le service de votre choix :"
                            # footer_text = "Veuillez Choisir le service de votre choix :"

                            payload = {
                                "messaging_product": "whatsapp",
                                "to": sender,
                                "type": "interactive",
                                "interactive": {
                                    "type": "list",
                                    "body": {"text": text.strip()},
                                    # "footer": {"text": footer_text},
                                    "action": {
                                        "button": "Afficher le menu",
                                        "sections": [
                                            {
                                                "title": "Seleccione desde aquí",
                                                "rows": [
                                                    {
                                                    "id": "role_driver1",
                                                    "title": "Envoyer un colis"
                                                    },
                                                    {
                                                    "id": "role_customer2",
                                                    "title": "Aller à l’aéroport"
                                                    },
                                                    {
                                                    "id": "role_driver3",
                                                    "title": "Retour de l’aéroport"
                                                    },
                                                    {
                                                    "id": "role_customer4",
                                                    "title": "Autres services"
                                                    }

                                                ],
                                            }
                                        ]
                                    },
                                },
                            }

                            # Update state for next step
                            set_state(sender, "service_selected")

                            # Send message to WhatsApp (sync httpx client for Flask route)
                            send_whatsapp_message(sender, payload, headers, url)
                            

                            return "ok", 200

                        else:
                            text = "❌ Demande annulée. Si vous souhaitez recommencer, n'hésitez pas à me le faire savoir !"
                            # clear_state(sender)
                            # clear_data(sender)

                        payload = {
                            "messaging_product": "whatsapp",
                            "to": sender,
                            "type": "text",
                            "text": {
                                "body": text.strip()
                            }
                        }
                        # Send message to WhatsApp (sync httpx client for Flask route)
                        send_whatsapp_message(sender, payload, headers, url)

                        increment_error_count(sender)
                        if get_error_count_exceeds_3(sender):
                            clear_all(sender)
                            clear_error_count(sender)
                            print("⚠️ Too many errors. Resetting conversation.")

                        return "ok", 200
                    
                    else:
                        # Here you would typically save the collected info to your database and/or proceed with the next steps of your flow
                        # Build and send summary
                        text = build_summary(sender)
                        ## You can build a nice summary of the collected info here to show to the user before confirming the request
                        payload = {
                            "messaging_product": "whatsapp",
                            "to": sender,
                            "type": "interactive",
                            "interactive": {
                                "type": "button",
                                "body": {
                                    "text": text.strip()
                                },
                                "action": {
                                    "buttons": [
                                        {
                                            "type": "reply",
                                            "reply": {
                                                "id": "parcel_req_Oui",
                                                "title": "Oui"
                                            }
                                        },
                                        {
                                            "type": "reply",
                                            "reply": {
                                                "id": "parcel_req_Non",
                                                "title": "Non"
                                            }
                                        }
                                    ]
                                }
                            }
                        }
                        
                        # Send message to WhatsApp (sync httpx client for Flask route)
                        send_whatsapp_message(sender, payload, headers, url)
                        
                        set_state(sender, "request_confirmation")
                        
                        return "ok", 200

                else:
                    print("⚠️ Message received in unknown state. Resetting conversation.")
                    clear_all(sender)
                    return "ok", 200

    except httpx.HTTPStatusError as e:
        # Graph API returned non-2xx
        print("❌ WhatsApp API error:", str(e))
        return "ok", 500

    except Exception as e:
        print("❌ Error:", str(e))
        return "ok", 500


