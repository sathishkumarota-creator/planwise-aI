# PocketSmart AI: Your Smart Budget & Recommendation Assistant

**PocketSmart AI** is a GenAI-powered cross-platform recommendation system that delivers personalized, budget-based suggestions for home decor, event planning, and jewelry shopping. Powered by **Google Gemini 1.5 Flash Pro**, **FastAPI**, and a modern responsive interface, it sources recommendations from top platforms including Amazon, Flipkart, IKEA, Swiggy, Zomato, OYO, Booking.com, BookMyShow, Tanishq, CaratLane, and more.

---

## 🌟 Key Features

1. **Home Interior Planning with Smart Budget Allocation (`/home-planner`)**:
   - Dynamic budget allocation across lighting fixtures, ceiling fans, furniture pieces, and dining tables.
   - Room-specific recommendations (Living Room, Kitchen, Bedroom).
   - Direct shopping links with pre-filled search terms for **IKEA India, Amazon, Flipkart, Myntra, and Ajio**.
   - Allocation breakdown calculation table and smart cost-saving recommendations.

2. **AI-Based Party Budget Planning (`/party-planner`)**:
   - Smart budget proportioning across catering, venue booking, theme decoration, entertainment, and contingency buffer.
   - Tailored to event types (Birthday, Wedding, Corporate, Anniversary) and guest count.
   - Sourcing links for **Swiggy, Zomato, BigBasket, BookMyShow, OYO, Booking.com, MakeMyTrip, and Amazon**.

3. **Jewelry Recommendations for Occasions (`/jewelry-planner`)**:
   - Context-aware recommendations for occasions (Wedding, Birthday, Festive, Cocktail, Casual).
   - **Multimodal Outfit Image Analysis**: Upload an outfit photo to automatically extract color palette, formality, and design style to match jewelry.
   - Sourcing links for **Tanishq, CaratLane, BlueStone, Melorra, Amazon, and Flipkart**.
   - Personalized styling and pairing tips.

4. **User Dashboard & History Tracking (`/dashboard`, `/history`)**:
   - Secure user authentication with JWT and Session cookies.
   - Full history of past recommendations with category filters and interactive details modal.
   - Pre-configured demo user (`sai` / `password123`) for instant testing.

---

## 🏗️ Architecture & Technology Stack

- **Backend**: FastAPI (Python 3.10+) with Uvicorn ASGI server
- **AI Engine**: Google Gemini 1.5 Flash Pro (`google-generativeai`) with intelligent offline rule-based fallback
- **Frontend**: HTML5, CSS3, Jinja2 Templates, FontAwesome Icons, Vanilla JS
- **Security**: OAuth2 Password Flow, JWT tokens (`python-jose`), bcrypt password hashing
- **Storage**: JSON-backed persistence for users and recommendation history

---

## 🚀 Getting Started

### 1. Requirements Installation
```bash
pip install -r requirements.txt
```

### 2. Environment Configuration
Create or modify `.env` (optional Google Gemini API key):
```env
GOOGLE_API_KEY=your_gemini_api_key_here
SECRET_KEY=pocketsmart_jwt_super_secret_key_2026_secure
HOST=0.0.0.0
PORT=8000
```
*(Note: If no API key is set, PocketSmart AI will automatically run in intelligent local fallback mode with realistic Indian pricing and platform search links).*

### 3. Run Application
```bash
python main.py
```
Or with Uvicorn:
```bash
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Open your browser at **[http://localhost:8000](http://localhost:8000)**.

### Demo Credentials
- **Username**: `sai`
- **Password**: `password123`
- *(Or register any new account on `/register`)*

---

## 📋 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Marketing Landing page |
| `GET`/`POST` | `/login` | User login and session initiation |
| `GET`/`POST` | `/register` | User registration |
| `POST` | `/token` | OAuth2 JWT token endpoint |
| `GET` | `/dashboard` | User dashboard with planner links & recent activity |
| `GET` | `/home-planner` | Home Interior Planner UI |
| `POST` | `/home-budget` or `/generate-home` | Generate home interior recommendations |
| `GET` | `/party-planner` | Party Planner UI |
| `POST` | `/party-budget` or `/generate-party` | Generate party budget plan |
| `GET` | `/jewelry-planner` | Jewelry Planner UI (with image upload) |
| `POST` | `/jewelry-budget` or `/generate-jewelry` | Generate jewelry recommendations |
| `GET` | `/history` | History page of saved recommendations |
| `GET` | `/recommendation-history` | JSON history list |
| `GET` | `/recommendation-details/{id}` | Detailed recommendation JSON |
| `GET` | `/session-info` | Current user session metadata |
| `GET` | `/logout` | Blacklist token and clear session |
