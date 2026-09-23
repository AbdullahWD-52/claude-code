"""Send alerts to your phone through a Telegram bot.

Setup (once):
  1. In Telegram, message @BotFather, send /newbot and copy the token it gives you.
  2. Put it in .env as TELEGRAM_BOT_TOKEN=...
  3. Send any message (e.g. "hi") to your new bot in Telegram.
  4. Run:  python notify.py --setup      (prints your chat id; put it in .env as TELEGRAM_CHAT_ID=...)
  5. Run:  python notify.py --test       (you should get a message on your phone)

If the two values are not set, alerts are silently skipped.
"""

import argparse
import json
import os
import urllib.parse
import urllib.request


def load_env(path=".env"):
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


def _api(method, **params):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(params).encode() if params else None
    with urllib.request.urlopen(url, data=data, timeout=10) as resp:
        return json.load(resp)


def send(text):
    """Send `text` to your Telegram chat. Never raises: an alert must not crash the bot."""
    if not os.environ.get("TELEGRAM_BOT_TOKEN") or not os.environ.get("TELEGRAM_CHAT_ID"):
        return False
    try:
        _api("sendMessage", chat_id=os.environ["TELEGRAM_CHAT_ID"], text=text)
        return True
    except Exception as e:  # noqa: BLE001 - any failure here is only logged
        print(f"(Telegram alert failed: {e})")
        return False


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--setup", action="store_true", help="print the chat id of whoever messaged your bot")
    p.add_argument("--test", action="store_true", help="send a test message")
    args = p.parse_args()
    load_env()

    if not os.environ.get("TELEGRAM_BOT_TOKEN"):
        print("TELEGRAM_BOT_TOKEN is missing in .env (see the steps at the top of this file).")
        return
    if args.setup:
        chats = {u["message"]["chat"]["id"]: u["message"]["chat"].get("first_name", "")
                 for u in _api("getUpdates").get("result", []) if "message" in u}
        if not chats:
            print("No messages found. Send any message to your bot in Telegram, then run this again.")
        for chat_id, name in chats.items():
            print(f"Chat id for {name or 'you'}: {chat_id}   ->  add TELEGRAM_CHAT_ID={chat_id} to .env")
    elif args.test:
        print("Sent! Check your phone." if send("Test alert from your Binance demo bot.")
              else "Not sent. Check TELEGRAM_CHAT_ID in .env.")
    else:
        p.print_help()


if __name__ == "__main__":
    main()
