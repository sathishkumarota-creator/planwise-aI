"""Marketplace registry.

The original code built shopping links with three near-identical functions full
of if/elif keyword matching. Here each marketplace is data and each planner
domain picks vendors per category *role*, so adding a vendor is a one-line
change instead of a new branch.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote_plus


@dataclass(frozen=True)
class Marketplace:
    key: str
    name: str
    url_template: str  # contains exactly one {} for the search query


_VENDORS: dict[str, Marketplace] = {
    m.key: m
    for m in (
        Marketplace("amazon", "Amazon India", "https://www.amazon.in/s?k={}"),
        Marketplace("flipkart", "Flipkart", "https://www.flipkart.com/search?q={}"),
        Marketplace("ikea", "IKEA India", "https://www.ikea.com/in/en/search/?q={}"),
        Marketplace("myntra", "Myntra", "https://www.myntra.com/search?q={}"),
        Marketplace("ajio", "Ajio", "https://www.ajio.com/search/?text={}"),
        Marketplace("meesho", "Meesho", "https://www.meesho.com/search?q={}"),
        Marketplace("swiggy", "Swiggy", "https://www.swiggy.com/search?query={}"),
        Marketplace("zomato", "Zomato", "https://www.zomato.com/search?q={}"),
        Marketplace("bigbasket", "BigBasket", "https://www.bigbasket.com/ps/?q={}"),
        Marketplace("bookmyshow", "BookMyShow", "https://in.bookmyshow.com/search?q={}"),
        Marketplace("oyorooms", "OYO Rooms", "https://www.oyorooms.com/search/?location={}"),
        Marketplace("booking", "Booking.com", "https://www.booking.com/search.html?ss={}"),
        Marketplace("makemytrip", "MakeMyTrip", "https://www.makemytrip.com/hotels/hotel-listing/?searchText={}"),
        Marketplace("tanishq", "Tanishq", "https://www.tanishq.co.in/search?q={}"),
        Marketplace("caratlane", "CaratLane", "https://www.caratlane.com/search?q={}"),
        Marketplace("bluestone", "BlueStone", "https://www.bluestone.com/search.html?query={}"),
        Marketplace("melorra", "Melorra", "https://www.melorra.com/search?q={}"),
        Marketplace("google", "Google", "https://www.google.com/search?q={}"),
    )
}

# domain -> role -> preferred vendors, in display order.
_SELECTION: dict[str, dict[str, tuple[str, ...]]] = {
    "home": {
        "any": ("ikea", "amazon", "flipkart", "myntra", "ajio"),
    },
    "event": {
        "venue": ("oyorooms", "booking", "makemytrip", "google"),
        "food": ("swiggy", "zomato", "bigbasket", "amazon"),
        "decor": ("amazon", "flipkart", "meesho", "myntra"),
        "entertainment": ("bookmyshow", "amazon", "flipkart"),
        "any": ("amazon", "flipkart", "google"),
    },
    "jewelry": {
        "any": ("tanishq", "caratlane", "bluestone", "melorra", "amazon", "flipkart"),
    },
}


def marketplace_links(domain: str, role: str, query: str) -> dict[str, str]:
    """Deep search links for `query` on the vendors suited to `domain`/`role`."""
    if not query:
        return {}
    encoded = quote_plus(query[:120])
    keys = _SELECTION.get(domain, _SELECTION["home"]).get(role) or _SELECTION[domain]["any"]
    links: dict[str, str] = {}
    for key in keys:
        vendor = _VENDORS.get(key)
        if vendor:
            links[vendor.key] = vendor.url_template.format(encoded)
    return links
