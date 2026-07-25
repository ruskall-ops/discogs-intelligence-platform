
from __future__ import annotations
from decimal import Decimal
import time
import requests

from dip import __version__


class DiscogsClient:
    def __init__(self, token: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Discogs token={token}",
            "User-Agent": f"RussellDiscogsIntelligencePlatform/{__version__}",
            "Accept": "application/vnd.discogs.v2.discogs+json",
        })

    def get_release(self, release_id: int):
        url = f"https://api.discogs.com/releases/{release_id}"
        for attempt in range(5):
            response = self.session.get(url, timeout=30)
            if response.status_code == 200:
                d = response.json(parse_float=Decimal)
                community = d.get("community")
                c = community if isinstance(community, dict) else {}
                lp = d.get("lowest_price")
                price = lp.get("value") if isinstance(lp, dict) else lp
                currency = (
                    lp.get("currency")
                    if isinstance(lp, dict)
                    else d.get("currency")
                )
                return {
                    "wants": _optional_integer(c.get("want")),
                    "haves": _optional_integer(c.get("have")),
                    "copies_for_sale": _optional_integer(d.get("num_for_sale")),
                    "lowest_price": _optional_exact_price(price),
                    "currency": currency,
                    "styles": _optional_joined_text(d, "styles"),
                    "genres": _optional_joined_text(d, "genres"),
                    "discogs_uri": _optional_uri(d.get("uri")),
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


def _optional_integer(value):
    if value is None:
        return None
    if type(value) is not int:
        raise TypeError("Discogs count must be an integer or null.")
    return value


def _optional_exact_price(value):
    if value is None or type(value) in {Decimal, int}:
        return value
    # Preserve only the unusable type classification. The canonical mapper
    # deliberately receives no arbitrary raw provider value.
    return object()


def _optional_joined_text(payload, key):
    if key not in payload or payload[key] is None:
        return None
    values = payload[key]
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        raise TypeError(f"Discogs {key} must be a list of strings or null.")
    return ", ".join(values)


def _optional_uri(value):
    if value is None or isinstance(value, str):
        return value
    raise TypeError("Discogs uri must be a string or null.")
