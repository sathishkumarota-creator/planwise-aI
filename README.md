# PlanWise

**PlanWise** is an AI-assisted budget planner that turns a total budget and a few
parameters (rooms, guests, occasion) into a concrete spending plan: category-wise
allocations, item suggestions with realistic Indian market prices, a calculation
table, and deep links into marketplaces such as Amazon India, Flipkart, IKEA,
Swiggy, Zomato, OYO, Booking.com, Tanishq, CaratLane, and more.

It covers three planning domains:

| Planner | What it allocates | Extras |
|---|---|---|
| **Home interiors** (`/planners/home`) | Lighting, ceiling fans, furniture, dining | Room scoping, preference notes, reserve for installation |
| **Events & parties** (`/planners/event`) | Venue, catering, decor, entertainment, contingency | Per-guest economics, venue suggestions |
| **Jewelry** (`/planners/jewelry`) | Necklace, earrings, bangle, ring by occasion weights | Optional outfit-photo color analysis (HSV palette) |

Plans are saved to per-user history with filters, a details modal, and CSV export.

---

## Architecture

```
app/
  config.py            Typed settings loaded once from the environment
  schemas.py           Pydantic contracts + unified report envelope
  security.py          bcrypt hashing, PyJWT tokens (stateless)
  uploads.py           Private photo storage: UUID names, type/size checks
  storage/             SQLite (WAL) + repository pattern
    database.py        Schema and connection factory
    users.py           UserRepository
    plans.py           PlanRepository
  services/
    engine.py          Planning pipeline: prompt -> AI -> sanitize -> catalog fallback
    ai_client.py       AiPlanner protocol: GeminiAiPlanner | NullAiPlanner
    marketplace.py     Data-driven marketplace registry (vendor links)
    palette.py         HSV-bucket outfit color analysis
    strategies/        One PlanningStrategy per domain + shared allocator
  web/
    app.py             create_app() factory, exception handlers
    deps.py            Page vs API auth dependencies
    templating.py      Jinja environment + `inr` currency filter
    routes/            pages, auth_pages, auth_api, plans_api
    templates/         base.html + per-page templates + planner forms
    static/            planwise.css (design tokens, dark mode), planwise.js
scripts/
  migrate_json_to_sqlite.py   One-shot importer from the legacy JSON store
main.py                Entrypoint
```

### Design decisions worth knowing

- **One API for three planners.** `POST /api/plans` takes a discriminated union
  (`spec.kind`), and every kind returns the same report envelope, so the UI and
  history render any plan with one code path.
- **Catalog strategies, not fixed percentages.** Each strategy declares desired
  purchases with realistic unit prices; the allocator scales them onto the
  spendable budget (quantities preserved, capped upscaling, visible reserve).
- **AI output is sanitized, never trusted.** Prices are clamped, totals are
  recomputed from items, malformed categories are dropped, and every plan is
  tagged `source: "gemini"` or `"catalog"`.
- **Uploads are private.** Photos live under `data/uploads/` (never web-served)
  and are shown through an authenticated proxy route.
- **Stateless auth.** JWT in an httpOnly cookie; no server-side session registry
  to clean up or lose on restart.

---

## Getting started

### 1. Requirements

Python 3.11+ (3.13 tested). Install dependencies:

```bash
pip install -r requirements.txt
```

### 2. Configuration

Create `.env` (all values optional except where noted):

```env
SECRET_KEY=change-me-in-production
GOOGLE_API_KEY=your_gemini_api_key_here   # optional; enables AI-generated plans
GEMINI_MODEL=gemini-1.5-flash
HOST=0.0.0.0
PORT=8000
TOKEN_TTL_MINUTES=120
UPLOAD_MAX_BYTES=5242880
CORS_ORIGINS=                              # comma-separated list; empty disables CORS
SEED_DEMO_USER=1
```

Without `GOOGLE_API_KEY` the app runs fully offline in catalog mode - the same
feature set, deterministic outputs.

### 3. Run

```bash
python main.py
# or: uvicorn main:app --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000**. Interactive API docs live at `/api/docs`.

### Demo account

- Username: `sai`
- Password: `password123`

(Or register a new account; passwords need 8+ characters with upper, lower,
and a digit.)

---

## API overview

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/plans` | Generate + save a plan (`spec.kind`: `home` / `event` / `jewelry`) |
| `GET` | `/api/plans` | List saved plans (`?kind=` filter) |
| `GET` | `/api/plans/{id}` | Full plan details |
| `DELETE` | `/api/plans/{id}` | Delete a plan |
| `GET` | `/api/plans/export.csv` | Export plan history |
| `POST` | `/api/plans/outfit-photo` | Upload an outfit photo, returns `photo_id` |
| `GET` | `/api/plans/photos/{id}` | Authenticated photo proxy |
| `POST` | `/api/token` | OAuth2-style token issuance |
| `GET` | `/api/me` | Current user |
| `GET/POST` | `/login`, `/register`, `/logout` | HTML auth flows |

## Migrating from the legacy JSON store

If you have a `data/database.json` from the previous version:

```bash
python scripts/migrate_json_to_sqlite.py
```

Users (with their existing bcrypt passwords) and plan history are imported;
legacy `party` plans are relabeled as `event` plans. The script is idempotent.
