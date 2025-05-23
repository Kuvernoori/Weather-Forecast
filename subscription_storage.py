import json
import os

FILE = "subscription.json"

def load_subscriptions():
    if not os.path.exists(FILE):
        return []

    with open(FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_subscriptions(subscriptions):
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(subscriptions, f)
