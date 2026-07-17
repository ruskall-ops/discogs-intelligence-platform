
from __future__ import annotations
import time
import requests

class DiscogsClient:
    def __init__(self, token: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Discogs token={token}",
            "User-Agent": "RussellDiscogsIntelligencePlatform/3.0",
            "Accept": "application/vnd.discogs.v2.discogs+json",
        })

    def get_release(self, release_id: int):
        url = f"https://api.discogs.com/releases/{release_id}"
        for attempt in range(5):
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                d = response.json()
                c = d.get("community") or {}
                lp = d.get("lowest_price")
                return {
                    "wants": int(c.get("want") or 0),
                    "haves": int(c.get("have") or 0),
                    "copies_for_sale": int(d.get("num_for_sale") or 0),
                    "lowest_price": float(
                        (lp.get("value") if isinstance(lp, dict) else lp) or 0
                    ),
                    "currency": lp.get("currency", "") if isinstance(lp, dict) else "",
                    "styles": ", ".join(d.get("styles") or []),
                    "genres": ", ".join(d.get("genres") or []),
                    "discogs_uri": d.get("uri", ""),
                }
            if response.status_code == 429:
                time.sleep(float(response.headers.get("Retry-After", "65")))
                continue
            if response.status_code in (500, 502, 503, 504):
                time.sleep(min(60, 2 ** (attempt + 1)))
                continue
            if response.status_code == 404:
                return None
            raise RuntimeError(f"Discogs API {response.status_code}: {response.text[:200]}")
        raise RuntimeError("Discogs API failed after repeated retries.")
