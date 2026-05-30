from telethon import TelegramClient, events
import re
import firebase_admin
from firebase_admin import credentials, db
from dotenv import load_dotenv
import os
from zoneinfo import ZoneInfo

load_dotenv()

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")

channel_username = os.getenv("CHANNEL_USERNAME")

database_url = os.getenv("DATABASE_URL")

client = TelegramClient("my_telegram_session", api_id, api_hash)
cred = credentials.Certificate("firebase-key.json")
firebase_admin.initialize_app(cred, {
    "databaseURL": database_url
})
firebase_ref = db.reference("signals")


def parse_signal_message(text):
    if not text:
        return None

    pair_match = re.search(r"PAIR:\s*#?([A-Z0-9]+)", text, re.IGNORECASE)
    type_match = re.search(r"TYPE:\s*(BUY|SELL)", text, re.IGNORECASE)
    entry_match = re.search(r"Entry:\s*([\d.]+)\s+([\d.]+)", text, re.IGNORECASE)
    tp1_match = re.search(r"TP1:\s*([\d.]+)", text, re.IGNORECASE)
    tp2_match = re.search(r"TP2:\s*([\d.]+)", text, re.IGNORECASE)
    sl_match = re.search(r"SL:\s*([\d.]+)", text, re.IGNORECASE)

    if not all([pair_match, type_match, entry_match, tp1_match, tp2_match, sl_match]):
        return None

    return {
        "pair": pair_match.group(1).upper(),
        "type": type_match.group(1).upper(),
        "entry_1": float(entry_match.group(1)),
        "entry_2": float(entry_match.group(2)),
        "tp1": float(tp1_match.group(1)),
        "tp2": float(tp2_match.group(1)),
        "sl": float(sl_match.group(1)),
    }


def save_signal_to_txt(message_id, date, signal_data):
    with open("valid_signals.txt", "a", encoding="utf-8") as file:
        file.write(f"Chanel ID: {channel_username}\n")
        file.write(f"Message ID: {message_id}\n")
        file.write(f"Date: {date}\n")
        file.write(f"Pair: {signal_data['pair']}\n")
        file.write(f"Type: {signal_data['type']}\n")
        file.write(f"Entry 1: {signal_data['entry_1']}\n")
        file.write(f"Entry 2: {signal_data['entry_2']}\n")
        file.write(f"TP1: {signal_data['tp1']}\n")
        file.write(f"TP2: {signal_data['tp2']}\n")
        file.write(f"SL: {signal_data['sl']}\n")
        file.write("-" * 40 + "\n")


def save_signal_to_firebase(message_id, date, signal_data):
    firebase_data = {
        "message_id": message_id,
        "pair": signal_data["pair"],
        "type": signal_data["type"],
        "entry_1": signal_data["entry_1"],
        "entry_2": signal_data["entry_2"],
        "tp1": signal_data["tp1"],
        "tp2": signal_data["tp2"],
        "sl": signal_data["sl"],
        "telegram_date": date.astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).strftime("%d/%m/%Y %H:%M:%S"),
    }

    firebase_ref.child(channel_username).child(str(message_id)).set(firebase_data)


@client.on(events.NewMessage(chats=channel_username))
async def handle_new_message(event):
    text = event.message.message

    signal_data = parse_signal_message(text)

    if signal_data is None:
        print("Ignored message. Not a signal format.")
        return

    message_id = event.message.id
    date = event.message.date

    print("Valid signal found:")
    print(signal_data)

    save_signal_to_txt(message_id, date, signal_data)
    save_signal_to_firebase(message_id, date, signal_data)

    print("Saved to txt and Firebase.")


print("Starting Telegram listener...")
client.start()
print("Listening for new valid signals...")
client.run_until_disconnected()
