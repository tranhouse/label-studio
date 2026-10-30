import os
import json
import requests
from pathlib import Path

# Configuration
BASE_URL = "http://ci-cdos-labelstudio-dev.ent.dfo-mpo.ca:8080"
PROJECT_ID = 61
TASK_ID = 1613
TOKEN = os.environ.get("LABEL_STUDIO_TOKEN")

INPUT_JSON = Path("sahi_results/0793_labelstudio.json")

if not TOKEN:
    raise ValueError("LABEL_STUDIO_TOKEN is not set.")

data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))

prediction_payload = {
    "task": TASK_ID,
    "model_version": data["predictions"][0]["model_version"],
    "result": data["predictions"][0]["result"]
}


# Exchange personal access token for a short-lived access token
auth_response = requests.post(
    f"{BASE_URL}/api/token/refresh",
    json={"refresh": TOKEN},
    timeout=30
)

print("Token refresh status:", auth_response.status_code)
auth_response.raise_for_status()

access_token = auth_response.json()["access"]

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

response = requests.post(
    f"{BASE_URL}/api/predictions/",
    headers=headers,
    json=prediction_payload
)

print("Status code:", response.status_code)
print("Response:")
print(response.text)