# Architecture — Namma Payana

## 1. Data flow

```
User → HTML/JS (browser) → Flask REST API (app.py)
         ↓
   Input Validation (services/validation.py — Pydantic v2)
         ↓
   Core Engine (deterministic, no AI)
   ┌──────────────────────────────────────┐
   │  ItineraryEngine  →  BudgetEngine    │
   │         ↓                 ↓          │
   │    FeasibilityEngine (scoring)       │
   │         ↓                            │
   │    ReplannerService (optional)       │
   └──────────────────────────────────────┘
         ↓
   SQLite (WAL mode) — services/db.py
         ↓
   JSON Response → browser

   Optional overlay (labelled, never affects engine output):
   AIPlannerService (Gemini) → narrative text only
   TranslatorService (lexicon → MyMemory → Gemini)
```

---

## 2. Engine invariants

- **No hallucinated data**: all destinations, distances, and fees come from `data/destinations.json` with source URLs.
- **Exact decimal arithmetic**: `BudgetEngine` uses Python `Decimal` throughout — no float rounding errors.
- **Schedule constraints**: `day_start=08:00`, `day_end=20:00`, pace-aware stops-per-day and active-hours caps enforced.
- **Coordinate bounds**: all destinations validated within Karnataka bounds (lat 11.5–18.5, lng 74.0–78.6).
- **Rest days**: trips exceeding pace capacity produce explicit rest days, not silent gaps.

---

## 3. AI boundary

**What AI can do**: write narrative descriptions for destinations, translate arbitrary text to Kannada via Gemini, enrich itinerary summaries with cultural context.

**What AI cannot do**: change destination IDs, alter timings or distances, affect feasibility scores, modify budget calculations, determine which destinations are included.

**Fallback chain**: if `GEMINI_API_KEY` is not set, AI provider = `"none"`; Kannada translation falls back to MyMemory API, then to the verified 42-phrase lexicon.

**Labelling**: all AI-generated content is flagged in the `ai_meta` field of API responses.

---

## 4. Authentication flow

- **Local password auth**: bcrypt-hashed passwords stored in SQLite `users` table. Registration rate-limited to 3/min, login to 5/min. Timing-constant login (dummy hash for missing users). Session stored in `httpOnly`, `SameSite=Lax` cookie.
- **Supabase JWT auth**: `/api/auth/google-check` validates a Bearer JWT against `SUPABASE_JWT_SECRET` using PyJWT, checks `email_verified` claim, then establishes a local session. Requires `SUPABASE_JWT_SECRET` to be configured.
- **Session lifecycle**: sessions expire after 24 hours (`PERMANENT_SESSION_LIFETIME`). `session.clear()` on login/logout to prevent session fixation.
- **CSRF**: `/api/csrf-token` endpoint issues tokens. Sensitive POST endpoints (register, login, logout) use `@csrf_protect_if_enabled`. `WTF_CSRF_CHECK_DEFAULT=False` so API clients are not broken.

---

## Authentication Architecture

### Local auth flow (PRIMARY)

`POST /api/auth/register` → validate input → bcrypt hash → store in SQLite `users` table → set session cookie.

This is the **primary** auth method. It is offline-capable and has no external dependencies. All session management, CSRF protection, and rate limiting are handled entirely within the Flask application.

### Google OAuth flow (ADDITIVE)

Supabase issues a JWT when the user signs in with Google on the frontend. The frontend sends that JWT to `POST /api/auth/google-check` as a Bearer token. The server verifies the JWT against `SUPABASE_JWT_SECRET` using PyJWT, checks the `email_verified` claim, then looks up the verified email in the local SQLite `users` table to establish a local session.

This is **additive**: Supabase only handles the OAuth handshake. All sessions are local.

### Why dual auth

The project originated as a hackathon prototype with local password auth. Supabase was added later to support Google login without replacing the local auth system. If the email does not already exist in the local database, the Google OAuth flow returns `NOT_REGISTERED` — the user must register first via the local flow.

### Future direction (Phase 15.1)

Recommended unification path: keep local password auth, add Supabase email verification for the registration flow, and drop the raw Supabase client from the frontend entirely. This keeps the backend self-contained and removes the frontend's direct dependency on Supabase JS SDK.

---

## 5. Routing provider chain

OSRM (if `OSRM_BASE_URL` configured) → Haversine fallback (always available, offline).

Ghat road multiplier (0.70×) applied for 10 known mountain-road destinations.
Monsoon multiplier (0.80×) applied when `start_date` falls in June–September.
`ROAD_DETOUR_FACTOR = 1.3` applied to Haversine distances to approximate road network length.

---

## 6. Security layers

- **Input validation**: Pydantic v2 models (`JourneyDNA`, `ReplanRequest`, `TripSaveRequest`) reject malformed input before any engine call.
- **CSRF**: Flask-WTF token on browser-facing POST endpoints.
- **Rate limiting**: Flask-Limiter in-memory store (register: 3/min, login: 5/min, generate: 20/min, translate: 10/min).
- **CSP**: per-request nonce, `script-src` restricted, `object-src none`, `frame-ancestors none`.
- **CORS**: explicit allowlist from `ALLOWED_ORIGINS` env var.
- **Ownership checks**: trips tied to `user_id`; `edit_token` required for guest-owned trips; `hmac.compare_digest` for token comparison.
- **No hardcoded secrets**: `config.py` reads all credentials from environment; production guard raises `RuntimeError` if `SECRET_KEY` is default.
