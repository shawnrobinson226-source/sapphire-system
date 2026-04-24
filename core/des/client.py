# core/des/client.py

import requests

DES_BASE_URL = "http://127.0.0.1:8000"


def check_trigger(payload):
    try:
        res = requests.post(f"{DES_BASE_URL}/trigger/check", json=payload)
        return res.json()
    except Exception:
        return {"show": False}


def start_interaction(payload):
    try:
        res = requests.post(f"{DES_BASE_URL}/interaction/start", json=payload)
        return res.json()
    except Exception:
        return {"error": "DES unavailable"}


def answer_interaction(payload):
    try:
        res = requests.post(f"{DES_BASE_URL}/interaction/answer", json=payload)
        return res.json()
    except Exception:
        return {"error": "DES unavailable"}