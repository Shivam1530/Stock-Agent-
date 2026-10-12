"""Minimal Groww live quote client, using only the Python standard library."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://api.groww.in/v1/live-data/quote"


def get_quote(trading_symbol: str) -> dict:
    token = os.environ.get("GROWW_ACCESS_TOKEN")
    if not token:
        raise SystemExit("Set GROWW_ACCESS_TOKEN to a current Groww API access token.")
    if not trading_symbol.strip():
        raise SystemExit("Groww trading symbol cannot be empty.")

    query = urllib.parse.urlencode({
        "exchange": "NSE",
        "segment": "CASH",
        "trading_symbol": trading_symbol,
    })
    req = urllib.request.Request(
        f"{BASE_URL}?{query}",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            "X-API-VERSION": "1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.load(response)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Groww quote request failed (HTTP {e.code}). Check token, subscription, and symbol.") from None
    except (urllib.error.URLError, TimeoutError) as e:
        raise SystemExit(f"Could not reach Groww quote API: {e.reason if isinstance(e, urllib.error.URLError) else e}") from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise SystemExit("Groww returned an invalid JSON response.") from None

    if not isinstance(data, dict) or data.get("status") != "SUCCESS" or not isinstance(data.get("payload"), dict):
        status = data.get("status", "unknown") if isinstance(data, dict) else "unknown"
        raise SystemExit(f"Groww quote request was not successful (status={status}).")
    return data["payload"]
