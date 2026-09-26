import os
import json
import re
import urllib.parse
from io import BytesIO
from typing import Optional, Dict, Any, List
from PIL import Image
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

gemini_model = None
gemini_available = False

if API_KEY and API_KEY.strip() and not API_KEY.startswith("your_"):
    try:
        import google.generativeai as genai
        genai.configure(api_key=API_KEY.strip())
        # Try latest recommended models: gemini-1.5-flash, gemini-1.5-pro
        gemini_model = genai.GenerativeModel("gemini-1.5-flash")
        gemini_available = True
    except Exception as e:
        print(f"[Warning] Failed to initialize Google Gemini client: {e}")
        gemini_available = False


def extract_json_from_response(text: str) -> dict:
    """Extract and parse JSON from AI response, handling markdown blocks."""
    try:
        # Check for ```json ... ```
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if json_match:
            clean_text = json_match.group(1).strip()
            return json.loads(clean_text)
        
        # Check first { to last }
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            clean_text = text[start:end+1].strip()
            return json.loads(clean_text)
            
        return json.loads(text.strip())
    except Exception as e:
        print(f"Error parsing JSON from response: {e}\nRaw text: {text[:200]}")
        raise ValueError(f"Could not parse valid JSON from AI response: {str(e)}")


def get_home_shopping_links(search_terms: str) -> dict:
    """Generate Indian e-commerce search links for home decor & furniture."""
    q = urllib.parse.quote_plus(search_terms)
    return {
        "amazon": f"https://www.amazon.in/s?k={q}",
        "flipkart": f"https://www.flipkart.com/search?q={q}",
        "ikea": f"https://www.ikea.com/in/en/search/?q={q}",
        "myntra": f"https://www.myntra.com/search?q={q}",
        "ajio": f"https://www.ajio.com/search/?text={q}"
    }


def get_party_shopping_links(category: str, search_terms: str) -> dict:
    """Generate platform-specific links for party planning categories."""
    q = urllib.parse.quote_plus(search_terms)
    links = {}
    cat = category.lower()

    if any(k in cat for k in ["venue", "hall", "resort", "hotel", "stay"]):
        links["google"] = f"https://www.google.com/search?q={q}"
        links["booking"] = f"https://www.booking.com/search.html?ss={q}"
        links["makemytrip"] = f"https://www.makemytrip.com/hotels/hotel-listing/?searchText={q}"
        links["oyorooms"] = f"https://www.oyorooms.com/search/?location={q}"
        links["nobroker"] = f"https://www.nobroker.in/property/search?searchTerm={q}"
    elif any(k in cat for k in ["catering", "food", "meal", "cake", "snack"]):
        links["swiggy"] = f"https://www.swiggy.com/search?query={q}"
        links["zomato"] = f"https://www.zomato.com/search?q={q}"
        links["bigbasket"] = f"https://www.bigbasket.com/ps/?q={q}"
        links["amazon"] = f"https://www.amazon.in/s?k={q}"
    elif any(k in cat for k in ["decor", "balloon", "flower", "lighting", "banner"]):
        links["amazon"] = f"https://www.amazon.in/s?k={q}"
        links["flipkart"] = f"https://www.flipkart.com/search?q={q}"
        links["meesho"] = f"https://www.meesho.com/search?q={q}"
        links["myntra"] = f"https://www.myntra.com/search?q={q}"
    elif any(k in cat for k in ["entertainment", "dj", "music", "game", "show", "artist"]):
        links["bookmyshow"] = f"https://in.bookmyshow.com/search?q={q}"
        links["amazon"] = f"https://www.amazon.in/s?k={q}"
        links["flipkart"] = f"https://www.flipkart.com/search?q={q}"
    else:
        links["amazon"] = f"https://www.amazon.in/s?k={q}"
        links["flipkart"] = f"https://www.flipkart.com/search?q={q}"
        links["google"] = f"https://www.google.com/search?q={q}"

    return links


def get_jewelry_shopping_links(search_terms: str) -> dict:
    """Generate shopping links for top Indian jewelry platforms."""
    q = urllib.parse.quote_plus(search_terms)
    return {
        "amazon": f"https://www.amazon.in/s?k={q}",
        "flipkart": f"https://www.flipkart.com/search?q={q}",
        "bluestone": f"https://www.bluestone.com/search.html?query={q}",
        "tanishq": f"https://www.tanishq.co.in/search?q={q}",
        "caratlane": f"https://www.caratlane.com/search?q={q}",
        "melorra": f"https://www.melorra.com/search?q={q}",
        "meesho": f"https://www.meesho.com/search?q={q}"
    }


def analyze_image_colors_fallback(image_path: str) -> dict:
    """Extract dominant color palette and aesthetic when running locally."""
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB")
            img = img.resize((50, 50))
            colors = img.getcolors(maxcolors=2500)
            if not colors:
                return {"colors": ["Navy Blue", "Emerald Green", "Gold"], "style": "Elegant Festive", "formality": "Formal"}
            # Sort by count
            sorted_colors = sorted(colors, key=lambda c: c[0], reverse=True)
            
            # Map top RGBs to human readable names
            names = []
            for count, (r, g, b) in sorted_colors[:8]:
                if r > 180 and g > 180 and b > 180:
                    name = "White / Cream"
                elif r < 40 and g < 40 and b < 40:
                    name = "Black / Deep Navy"
                elif r > 160 and g < 70 and b < 70:
                    name = "Crimson Red"
                elif r < 70 and g > 130 and b < 70:
                    name = "Emerald Green"
                elif r < 60 and g < 100 and b > 150:
                    name = "Royal Blue"
                elif r > 180 and g > 150 and b < 80:
                    name = "Golden Ochre"
                elif r > 180 and g < 120 and b > 150:
                    name = "Magenta / Pink"
                elif r > 120 and g < 60 and b > 120:
                    name = "Purple"
                else:
                    name = f"RGB({r},{g},{b})"
                if name not in names and not name.startswith("RGB"):
                    names.append(name)
            
            if not names:
                names = ["Emerald Green", "Navy Blue", "Gold Accent"]

            return {
                "colors": names[:3],
                "style": "Sophisticated Evening / Occasion Wear",
                "formality": "Formal"
            }
    except Exception as e:
        print(f"Image analysis error: {e}")
        return {"colors": ["Emerald Green", "Navy Blue"], "style": "Festive", "formality": "Semi-Formal"}


def generate_fallback_home_recommendations(budget_input: Any) -> dict:
    """Smart fallback generator adhering strictly to the required schema."""
    total_budget = float(budget_input.total_budget)
    num_lights = getattr(budget_input, 'num_lights', 2) or 2
    num_fans = getattr(budget_input, 'num_fans', 1) or 1
    num_furniture = getattr(budget_input, 'num_furniture', 1) or 1
    num_dining = getattr(budget_input, 'num_dining_tables', 0) or 0
    has_living = getattr(budget_input, 'has_living_room', True)
    has_kitchen = getattr(budget_input, 'has_kitchen', False)
    has_bedroom = getattr(budget_input, 'has_bedroom', False)

    categories = []
    
    # 1. Lighting category
    light_unit_price = round((total_budget * 0.15) / max(num_lights, 1), 2)
    categories.append({
        "category": "Lighting",
        "allocation": round(light_unit_price * num_lights, 2),
        "items": [
            {
                "name": "Philips / Crompton LED Warm White Lights",
                "description": "Energy-efficient LED ambient ceiling lighting for cozy room aesthetics.",
                "estimated_price": light_unit_price,
                "quantity": num_lights,
                "search_terms": "Warm White LED Ceiling Light fixture"
            }
        ]
    })

    # 2. Ceiling Fans category
    if num_fans > 0:
        fan_unit_price = round((total_budget * 0.20) / max(num_fans, 1), 2)
        categories.append({
            "category": "Ceiling Fans",
            "allocation": round(fan_unit_price * num_fans, 2),
            "items": [
                {
                    "name": "Havells / Atomberg BLDC Energy Saver Ceiling Fan",
                    "description": "Silent, high-airflow BLDC ceiling fan with remote control.",
                    "estimated_price": fan_unit_price,
                    "quantity": num_fans,
                    "search_terms": "Atomberg BLDC silent ceiling fan"
                }
            ]
        })

    # 3. Furniture
    if num_furniture > 0:
        furn_unit_price = round((total_budget * 0.35) / max(num_furniture, 1), 2)
        categories.append({
            "category": "Furniture",
            "allocation": round(furn_unit_price * num_furniture, 2),
            "items": [
                {
                    "name": "Ergonomic Lounge Chairs / Modular Side Unit",
                    "description": "High-density cushioned seating with solid wood accents.",
                    "estimated_price": furn_unit_price,
                    "quantity": num_furniture,
                    "search_terms": "Modern Accent Armchair solid wood"
                }
            ]
        })

    # 4. Dining Table
    if num_dining > 0:
        dining_unit_price = round((total_budget * 0.20) / max(num_dining, 1), 2)
        categories.append({
            "category": "Dining Furniture",
            "allocation": round(dining_unit_price * num_dining, 2),
            "items": [
                {
                    "name": "Compact Engineered Wood Dining Table",
                    "description": "Minimalist dining setup suitable for apartment living.",
                    "estimated_price": dining_unit_price,
                    "quantity": num_dining,
                    "search_terms": "Modern 4 seater dining table wooden"
                }
            ]
        })

    # Calculate totals
    total_allocated = sum(c["allocation"] for c in categories)
    if total_allocated > total_budget:
        ratio = (total_budget * 0.90) / total_allocated
        for c in categories:
            c["allocation"] = round(c["allocation"] * ratio, 2)
            for itm in c["items"]:
                itm["estimated_price"] = round(c["allocation"] / max(itm["quantity"], 1), 2)
        total_allocated = sum(c["allocation"] for c in categories)

    remaining_budget = max(0.0, round(total_budget - total_allocated, 2))

    calc_table = []
    for c in categories:
        items_cnt = sum(itm["quantity"] for itm in c["items"])
        pct = round((c["allocation"] / total_budget) * 100, 1) if total_budget > 0 else 0
        calc_table.append({
            "category": c["category"],
            "items_count": items_cnt,
            "total_cost": c["allocation"],
            "percentage_of_budget": pct
        })

    result = {
        "total_budget": total_budget,
        "budget_breakdown": categories,
        "calculation_table": calc_table,
        "remaining_budget": remaining_budget,
        "additional_suggestions": [
            "Consider purchasing modular furniture for future flexibility.",
            "Compare festive clearance deals across IKEA India and Amazon for lighting packages.",
            "Choose BLDC 5-star fans to reduce electricity bills by up to 65% annually.",
            "Prioritize living room focal points first before kitchen accessorizing."
        ]
    }
    return result


def generate_fallback_party_recommendations(budget_input: Any) -> dict:
    """Smart fallback generator for party budget planner."""
    total_budget = float(budget_input.total_budget)
    num_guests = int(getattr(budget_input, 'num_guests', 10) or 10)
    party_type = getattr(budget_input, 'party_type', 'Birthday') or 'Birthday'
    venue_type = getattr(budget_input, 'venue_type', 'Home') or 'Home'

    catering_share = 0.40 if getattr(budget_input, 'needs_catering', True) else 0.05
    decor_share = 0.20 if getattr(budget_input, 'needs_decoration', True) else 0.05
    entertain_share = 0.20 if getattr(budget_input, 'needs_entertainment', True) else 0.05
    venue_share = 0.10 if venue_type.lower() != "home" else 0.05
    contingency_share = max(0.05, 1.0 - (catering_share + decor_share + entertain_share + venue_share))

    venue_amt = round(total_budget * venue_share, 2)
    catering_amt = round(total_budget * catering_share, 2)
    decor_amt = round(total_budget * decor_share, 2)
    entertain_amt = round(total_budget * entertain_share, 2)
    contingency_amt = round(total_budget * contingency_share, 2)

    categories = [
        {
            "category": "Venue",
            "allocation": venue_amt,
            "items": [
                {
                    "name": f"{venue_type} Event Space / Arrangement",
                    "description": f"Space booking and prep suited for {num_guests} guests for a {party_type}.",
                    "estimated_price": venue_amt,
                    "quantity": 1,
                    "search_terms": f"{venue_type} venue near me for {party_type}"
                }
            ]
        },
        {
            "category": "Catering",
            "allocation": catering_amt,
            "items": [
                {
                    "name": f"Gourmet Food & Snack Box ({num_guests} guests)",
                    "description": f"Appetizers, main courses, and signature desserts priced at approx ₹{round(catering_amt/max(num_guests,1), 2)}/head.",
                    "estimated_price": catering_amt,
                    "quantity": num_guests,
                    "search_terms": f"Bulk party food catering snacks and meals"
                }
            ]
        },
        {
            "category": "Decoration",
            "allocation": decor_amt,
            "items": [
                {
                    "name": f"{party_type} Theme Decoration Kit",
                    "description": "Balloon arch, backdrop curtain, fairy lights, and themed celebration banner.",
                    "estimated_price": decor_amt,
                    "quantity": 1,
                    "search_terms": f"{party_type} decoration party kit balloons lights"
                }
            ]
        },
        {
            "category": "Entertainment",
            "allocation": entertain_amt,
            "items": [
                {
                    "name": "Audio System / Party Games & Streaming",
                    "description": "Curated playlist speaker rental, group trivia games, and party music pass.",
                    "estimated_price": entertain_amt,
                    "quantity": 1,
                    "search_terms": "Party bluetooth speaker rental and board games"
                }
            ]
        },
        {
            "category": "Contingency",
            "allocation": contingency_amt,
            "items": [
                {
                    "name": "Buffer for Extra Guests & Supplies",
                    "description": "Emergency budget for extra drinks, disposables, ice, and unforeseen transport.",
                    "estimated_price": contingency_amt,
                    "quantity": 1,
                    "search_terms": "Party disposable tableware cups napkins set"
                }
            ]
        }
    ]

    total_allocated = sum(c["allocation"] for c in categories)
    remaining_budget = max(0.0, round(total_budget - total_allocated, 2))

    calc_table = []
    for c in categories:
        items_cnt = sum(itm["quantity"] for itm in c["items"])
        pct = round((c["allocation"] / total_budget) * 100, 1) if total_budget > 0 else 0
        calc_table.append({
            "category": c["category"],
            "items_count": items_cnt,
            "total_cost": c["allocation"],
            "percentage_of_budget": pct
        })

    venue_sugg = [
        {
            "name": f"{venue_type} Celebration Spot",
            "type": venue_type,
            "capacity": num_guests,
            "estimated_cost": venue_amt,
            "search_terms": f"{venue_type} booking for party {party_type}"
        }
    ]

    return {
        "total_budget": total_budget,
        "budget_breakdown": categories,
        "calculation_table_inr": calc_table,
        "venue_suggestions": venue_sugg,
        "remaining_budget": remaining_budget,
        "additional_suggestions": [
            "Order catering 48 hours in advance through Swiggy / Zomato party platters to get bulk discounts.",
            "Create a collaborative Spotify party playlist so guests can queue their favorite tracks.",
            "Use DIY reusable LED strip lights and balloon garlands to save up to 40% on decoration costs."
        ]
    }


def generate_fallback_jewelry_recommendations(budget_input: Any, outfit_info: Optional[dict] = None) -> dict:
    """Smart fallback generator for jewelry budget planner."""
    total_budget = float(budget_input.total_budget)
    occasion = getattr(budget_input, 'occasion', 'Wedding / Festive') or 'Festive'
    preferences = getattr(budget_input, 'preferences', 'Elegant') or 'Elegant'

    colors = outfit_info.get("colors", ["Emerald Green", "Gold Accent"]) if outfit_info else ["Emerald Green", "Gold"]
    style = outfit_info.get("style", preferences or "Ethnic Modern") if outfit_info else preferences
    formality = outfit_info.get("formality", "Formal") if outfit_info else "Semi-Formal"

    # Jewelry items list with realistic price breakdown
    items = []
    earring_price = round(total_budget * 0.35, 2)
    necklace_price = round(total_budget * 0.40, 2)
    bracelet_price = round(total_budget * 0.15, 2)
    ring_price = round(total_budget * 0.05, 2)

    items.append({
        "item_type": "Necklace",
        "description": f"Intricate statement choker / pendant set complementing {colors[0]} tones.",
        "style": style,
        "estimated_price": necklace_price,
        "search_terms": f"{occasion} {style} necklace set {colors[0]}"
    })
    items.append({
        "item_type": "Earrings",
        "description": f"Chandelier / Jhumka drop earrings engineered with fine Kundan or stone work.",
        "style": style,
        "estimated_price": earring_price,
        "search_terms": f"{occasion} {style} drop earrings jhumka"
    })
    items.append({
        "item_type": "Bracelet / Bangle",
        "description": f"Delicate filigree kada or tennis bracelet with subtle shimmer.",
        "style": style,
        "estimated_price": bracelet_price,
        "search_terms": f"{style} gold plated bracelet kada"
    })
    items.append({
        "item_type": "Statement Ring",
        "description": f"Solitaire or cocktail floral ring matching the {occasion} dress aesthetic.",
        "style": style,
        "estimated_price": ring_price,
        "search_terms": f"Cocktail statement ring adjustable"
    })

    allocated = necklace_price + earring_price + bracelet_price + ring_price
    remaining = max(0.0, round(total_budget - allocated, 2))

    return {
        "outfit_analysis": {
            "colors": colors,
            "style": style,
            "formality": formality
        },
        "total_budget": total_budget,
        "jewelry_recommendations": items,
        "remaining_budget": remaining,
        "styling_tips": [
            f"Since your outfit features {', '.join(colors)}, warm gold and pearl highlights will create the most flattering contrast.",
            "Balance your jewelry: if wearing an elaborate necklace, pair it with subtle drop earrings to avoid overwhelming your look.",
            "Opt for hallmark certified lightweight silver or 14k/18k vermeil from CaratLane or Tanishq for guaranteed durability.",
            f"For a {occasion} setting, a statement cocktail ring adds sophistication without interfering with sleeve embroidery."
        ]
    }


def get_home_recommendations(budget_input: Any) -> dict:
    """Generate home interior recommendations within budget in INR/USD."""
    total_budget = float(budget_input.total_budget)
    num_lights = getattr(budget_input, 'num_lights', 0)
    num_fans = getattr(budget_input, 'num_fans', 0)
    num_furniture = getattr(budget_input, 'num_furniture', 0)
    num_dining = getattr(budget_input, 'num_dining_tables', 0)
    has_living = getattr(budget_input, 'has_living_room', False)
    has_kitchen = getattr(budget_input, 'has_kitchen', False)
    has_bed = getattr(budget_input, 'has_bedroom', False)
    add_req = getattr(budget_input, 'additional_requirements', "None") or "None"

    rooms_list = []
    if has_living: rooms_list.append("Living room")
    if has_kitchen: rooms_list.append("Kitchen")
    if has_bed: rooms_list.append("Bedroom")
    rooms_str = ", ".join(rooms_list) if rooms_list else "General home interior"

    prompt = f"""
I need interior design product recommendations for a home in India with a total budget of ₹{total_budget:.2f}.
Requirements:
- {num_lights} lights/lighting fixtures
- {num_fans} ceiling fans
- {num_furniture} furniture pieces
- {num_dining} dining tables
Additional rooms to consider: {rooms_str}
Additional requirements: {add_req}

Please provide a detailed budget breakdown with product recommendations **available in India**.
Use **Indian brands and pricing**. Include **search terms** suitable for Indian shopping platforms.

Format your response as pure JSON with the following structure:
{{
  "total_budget": {total_budget:.2f},
  "budget_breakdown": [
    {{
      "category": "Lighting",
      "allocation": 0.0,
      "items": [
        {{
          "name": "Product name",
          "description": "Item description",
          "estimated_price": 0.0,
          "quantity": 1,
          "search_terms": "search query"
        }}
      ]
    }}
  ],
  "calculation_table": [
    {{
      "category": "Lighting",
      "items_count": 1,
      "total_cost": 0.0,
      "percentage_of_budget": 0.0
    }}
  ],
  "remaining_budget": 0.0,
  "additional_suggestions": [
    "Tip 1",
    "Tip 2"
  ]
}}
Ensure total costs stay within budget. Do not return any extra explanation outside the JSON.
"""
    result = None
    if gemini_available and gemini_model:
        try:
            response = gemini_model.generate_content(prompt)
            result = extract_json_from_response(response.text)
        except Exception as e:
            print(f"[Gemini API fallback] Error in home recommendation call: {e}")
            result = None

    if not result or "budget_breakdown" not in result:
        result = generate_fallback_home_recommendations(budget_input)

    # Attach shopping links
    for category in result.get("budget_breakdown", []):
        for item in category.get("items", []):
            search_terms = item.get("search_terms") or item.get("name", "")
            item["shopping_links"] = get_home_shopping_links(search_terms)

    return result


def get_party_recommendations(budget_input: Any) -> dict:
    """Generate party planning recommendations within budget for Indian market."""
    total_budget = float(budget_input.total_budget)
    num_guests = getattr(budget_input, 'num_guests', 10)
    party_type = getattr(budget_input, 'party_type', 'Birthday')
    venue_type = getattr(budget_input, 'venue_type', 'Home')
    needs_catering = "Yes" if getattr(budget_input, 'needs_catering', True) else "No"
    needs_decoration = "Yes" if getattr(budget_input, 'needs_decoration', True) else "No"
    needs_entertainment = "Yes" if getattr(budget_input, 'needs_entertainment', True) else "No"
    add_req = getattr(budget_input, 'additional_requirements', "None") or "None"

    prompt = f"""
I need party planning recommendations for India with a total budget of ₹{total_budget:.2f}.
Party details:
- Type: {party_type}
- Number of guests: {num_guests}
- Venue type: {venue_type}
- Catering needed: {needs_catering}
- Decoration needed: {needs_decoration}
- Entertainment needed: {needs_entertainment}
Additional requirements: {add_req}

Please provide a detailed budget breakdown with specific recommendations available in India using INR prices.
Use Indian brands, services, and typical cost expectations.

Format your response as pure JSON with the following structure:
{{
  "total_budget": {total_budget:.2f},
  "budget_breakdown": [
    {{
      "category": "Venue",
      "allocation": 0.0,
      "items": [
        {{
          "name": "Item name",
          "description": "Item description",
          "estimated_price": 0.0,
          "quantity": 1,
          "search_terms": "search query"
        }}
      ]
    }}
  ],
  "venue_suggestions": [
    {{
      "name": "Venue Name",
      "type": "{venue_type}",
      "capacity": {num_guests},
      "estimated_cost": 0.0,
      "search_terms": "venue query"
    }}
  ],
  "remaining_budget": 0.0,
  "additional_suggestions": [
    "Suggestion 1",
    "Suggestion 2"
  ]
}}
Ensure all costs are in INR and total does not exceed the given budget.
Provide search terms suitable for Indian websites such as BookMyShow, Swiggy, Flipkart, etc.
"""
    result = None
    if gemini_available and gemini_model:
        try:
            response = gemini_model.generate_content(prompt)
            result = extract_json_from_response(response.text)
        except Exception as e:
            print(f"[Gemini API fallback] Error in party recommendation call: {e}")
            result = None

    if not result or "budget_breakdown" not in result:
        result = generate_fallback_party_recommendations(budget_input)

    # Attach calculation table if not present
    if not result.get("calculation_table_inr"):
        calc = []
        for cat in result.get("budget_breakdown", []):
            cnt = sum(itm.get("quantity", 1) for itm in cat.get("items", []))
            alloc = float(cat.get("allocation", 0))
            pct = round((alloc / total_budget) * 100, 1) if total_budget > 0 else 0
            calc.append({
                "category": cat.get("category", "General"),
                "items_count": cnt,
                "total_cost": alloc,
                "percentage_of_budget": pct
            })
        result["calculation_table_inr"] = calc

    # Attach shopping links by category
    for cat in result.get("budget_breakdown", []):
        cat_name = cat.get("category", "General")
        for item in cat.get("items", []):
            st = item.get("search_terms") or item.get("name", "")
            item["shopping_links"] = get_party_shopping_links(cat_name, st)

    for v in result.get("venue_suggestions", []):
        st = v.get("search_terms") or v.get("name", "")
        v["search_links"] = get_party_shopping_links("venue", st)

    return result


def get_jewelry_recommendations(budget_input: Any, image_path: Optional[str] = None) -> dict:
    """Generate jewelry recommendations with optional multimodal image analysis."""
    total_budget = float(budget_input.total_budget)
    occasion = getattr(budget_input, 'occasion', 'Wedding / Celebration')
    preferences = getattr(budget_input, 'preferences', 'Traditional and elegant') or 'Traditional and elegant'

    outfit_info = None
    if image_path and os.path.exists(image_path):
        outfit_info = analyze_image_colors_fallback(image_path)

    base_prompt = f"""
I need jewelry recommendations for India with a total budget of ₹{total_budget:.2f}.
Occasion: {occasion}
Preferences: {preferences}
Provide only India-relevant styles, availability, and price ranges in INR.
"""
    if image_path and os.path.exists(image_path):
        base_prompt += """
An image of the outfit is provided. Suggest jewelry that complements it, considering color, design, and occasion appropriateness.
"""

    prompt = base_prompt + f"""
Format the output as pure JSON:
{{
  "outfit_analysis": {{
    "colors": ["Primary Color", "Secondary Color"],
    "style": "Casual/Traditional/Western/Indo-Western",
    "formality": "Formal/Semi-Formal/Casual"
  }},
  "total_budget": {total_budget:.2f},
  "jewelry_recommendations": [
    {{
      "item_type": "Necklace / Earring / Ring / Bracelet",
      "description": "Detailed description of the jewelry piece",
      "style": "Traditional/Modern",
      "estimated_price": 0.0,
      "search_terms": "Search query for Indian shopping"
    }}
  ],
  "remaining_budget": 0.0,
  "styling_tips": [
    "Styling tip 1",
    "Styling tip 2"
  ]
}}
Keep prices in INR and relevant to Indian brands like Tanishq, CaratLane, BlueStone, Melorra.
"""
    result = None
    if gemini_available and gemini_model:
        try:
            if image_path and os.path.exists(image_path):
                with Image.open(image_path) as img:
                    response = gemini_model.generate_content([prompt, img])
            else:
                response = gemini_model.generate_content(prompt)
            result = extract_json_from_response(response.text)
        except Exception as e:
            print(f"[Gemini API fallback] Error in jewelry recommendation call: {e}")
            result = None

    if not result or "jewelry_recommendations" not in result:
        result = generate_fallback_jewelry_recommendations(budget_input, outfit_info)

    # Attach shopping links
    for item in result.get("jewelry_recommendations", []):
        st = item.get("search_terms") or item.get("item_type", "")
        item["shopping_links"] = get_jewelry_shopping_links(st)

    return result
