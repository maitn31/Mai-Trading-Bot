import MetaTrader5 as mt5
import firebase_admin
from firebase_admin import credentials, db
from dotenv import load_dotenv
import os

load_dotenv()

CHANNEL_NAME = os.getenv("CHANNEL_USERNAME")
DATABASE_URL = os.getenv("DATABASE_URL")
FIREBASE_KEY_FILE = "firebase-key.json"

LOT_SIZE = 0.01

SYMBOL_MAP = {
    "XAUUSD": "XAUUSDm"
}

seen_ids = set()
initial_load_done = False


def initialize_firebase():
    if not DATABASE_URL:
        print("DATABASE_URL is missing in .env")
        return False
    if not CHANNEL_NAME:
        print("CHANNEL_NAME is missing in .env")
        return False

    cred = credentials.Certificate(FIREBASE_KEY_FILE)

    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred, {
            "databaseURL": DATABASE_URL
        })

    print("Firebase connected")

    return True


def initialize_mt5():
    if not mt5.initialize():
        print("MT5 initialize failed:", mt5.last_error())
        return False

    print("MT5 connected")
    return True


def get_mt5_symbol(signal_pair):
    return SYMBOL_MAP.get(signal_pair, signal_pair)


def get_pending_order_type(signal_type, entry_price, tick):
    signal_type = signal_type.upper()

    if signal_type == "BUY":
        if entry_price < tick.ask:
            return mt5.ORDER_TYPE_BUY_LIMIT
        return mt5.ORDER_TYPE_BUY_STOP

    if signal_type == "SELL":
        if entry_price > tick.bid:
            return mt5.ORDER_TYPE_SELL_LIMIT
        return mt5.ORDER_TYPE_SELL_STOP

    return None


def place_order(signal_id, signal_data):
    signal_pair = signal_data.get("pair")
    signal_type = signal_data.get("type")

    if not signal_pair or not signal_type:
        print("Invalid signal data:", signal_data)
        return False

    symbol = get_mt5_symbol(signal_pair)

    entry_price = float(signal_data["entry_2"])
    tp = float(signal_data["tp2"])
    sl = float(signal_data["sl"])

    symbol_info = mt5.symbol_info(symbol)

    if symbol_info is None:
        print("Symbol not found:", symbol)
        return False

    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            print("Failed to select symbol:", symbol)
            return False

    tick = mt5.symbol_info_tick(symbol)

    if tick is None:
        print("Failed to get tick for:", symbol)
        return False

    order_type = get_pending_order_type(signal_type, entry_price, tick)

    if order_type is None:
        print("Invalid order type:", signal_type)
        return False

    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": LOT_SIZE,
        "type": order_type,
        "price": entry_price,
        "sl": sl,
        "tp": tp,
        "deviation": 20,
        "magic": 20260529,
        "comment": f"Firebase signal {signal_id}",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }

    print("Sending order request:")
    print(request)

    result = mt5.order_send(request)

    print("Order result:")
    print(result)

    if result is None:
        print("Order send returned None:", mt5.last_error())
        return False

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print("Order failed:", result.retcode, result.comment)
        return False

    print("Order placed successfully")
    return True


def handle_signal(signal_id, signal_data):
    if signal_id in seen_ids:
        print("Skipped duplicate signal:", signal_id)
        return

    seen_ids.add(signal_id)

    print("New signal received:")
    print("Channel:", CHANNEL_NAME)
    print("Signal ID:", signal_id)
    print(signal_data)

    place_order(signal_id, signal_data)


def firebase_listener(event):
    global initial_load_done

    print("Firebase event path:", event.path)

    if event.path == "/":
        print("Initial Firebase data loaded. Ignoring old signals.")

        if isinstance(event.data, dict):
            for signal_id in event.data.keys():
                seen_ids.add(str(signal_id))

        initial_load_done = True
        print("Ready. New signals after this point will be traded.")
        return

    if not initial_load_done:
        print("Ignored event because initial load is not done yet.")
        return

    if event.data is None:
        return

    signal_id = event.path.strip("/")

    if "/" in signal_id:
        return

    if not isinstance(event.data, dict):
        return

    handle_signal(signal_id, event.data)


def main():


    if not initialize_firebase():
        return

    if not initialize_mt5():
        return

    signals_ref = db.reference(f"signals/{CHANNEL_NAME}")

    print("Listening to Firebase signals")
    signals_ref.listen(firebase_listener)


if __name__ == "__main__":
    main()
