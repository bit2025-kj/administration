import time
import requests

# URL de ton backend FastAPI Render
URL = "https://administration-x4ak.onrender.com"

# Intervalle en secondes (5 minutes)
INTERVAL = 5 * 60

while True:
    try:
        r = requests.get(URL, timeout=10)
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Ping: {r.status_code}")
    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Erreur ping: {e}")
    time.sleep(INTERVAL)
