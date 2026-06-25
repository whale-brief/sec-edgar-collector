import os
import requests
import logging
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class WebhookClient:
    """
    A lightweight client to transmit extracted data to the central whale-brief-api server.
    """
    def __init__(self):
        # Base URL of the API server (e.g., http://localhost:8000/api/internal/webhooks)
        self.base_url = os.getenv("WEBHOOK_BASE_URL", "http://localhost:8000/api/internal/webhooks")
        self.headers = {
            "Content-Type": "application/json",
            "X-Internal-Token": os.getenv("INTERNAL_TOKEN", "super_secret_dev_token")
        }

    def send(self, endpoint: str, payload: Dict[str, Any]) -> bool:
        """
        Dispatches a JSON payload via POST to the specified webhook endpoint.
        """
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.post(url, json=payload, headers=self.headers, timeout=10)
            response.raise_for_status()
            logging.info(f"✅ Webhook Success: {endpoint} | Target: {payload.get('ticker', 'BATCH')}")
            return True
        except requests.exceptions.RequestException as e:
            logging.error(f"❌ Webhook Failed ({endpoint}): {e}")
            return False

# Singleton instance for easy import across modules
webhook_client = WebhookClient()