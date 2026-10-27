# Namma Payana — Beyond Destinations. Into Karnataka.

A deterministic, constraint-aware Karnataka travel planner. Born at a hackathon, hardened for production.

---

## Honest AI statement

The core engine — itinerary generation, budget calculation, feasibility scoring, and replanning — works entirely **offline with zero AI calls**. No LLM is consulted to pick destinations, compute distances, or decide whether a trip is feasible.

Google Gemini AI is used **only** for two narrow, optional purposes:
- Writing narrative prose for destination descriptions
- Translating arbitrary text to Kannada

Both functions require a configured `GEMINI_API_KEY`. If no key is present, `AI_PROVIDER` falls back to `"none"` and all narrative fields are omitted gracefully. Kannada translation falls back to the **MyMemory API**, then to the **verified 42-phrase lexicon** — which works with no external API at all.

All AI-generated content is flagged in the `ai_meta` field of API responses and **never affects** destination IDs, timings, distances, costs, or feasibility scores.

---

## Architecture overview

```
app.py               Flask REST API + Jinja2 templates
config.py            All configuration (env-driven, no hardcoded secrets)
services/
  itinerary.py       Deterministic day-by-day planner
  budget.py          Decimal-exact cost engine
  feasibility.py     0-100 constraint scoring
  replanner.py       Natural language trip modification
  routing.py         RoutingProvider (Haversine default, OSRM optional)
  trip_store.py      SQLite trip persistence
  user_store.py      SQLite user/auth storage
  db.py              Shared WAL-mode SQLite helper
  ai_planner.py      Gemini narrative enrichment (optional)
  translator.py      Kannada translation (lexicon + MyMemory + Gemini)
  validation.py      Pydantic v2 input models
data/
  destinations.json  52 verified Karnataka destinations
  kannada_phrases.json  42 verified Kannada expressions
static/js/
  app.js             Main frontend controller (escapeHtml XSS protection)
  auth.js            Supabase OAuth + local auth
  map.js             Leaflet interactive atlas
  phrases.js         Kannada companion
  i18n.js            6-language UI
templates/
  index.html         Single-page application shell
scripts/
  validate_data.py   Data integrity validator
tests/               119 tests across all modules
```

---

## Environment variables

| Variable | Description | Required / Optional | Default |
|---|---|---|---|
| `FLASK_ENV` | Runtime environment (`development` / `production`) | Optional | `development` |
| `PORT` | HTTP port to listen on | Optional | `5000` |
| `SECRET_KEY` | Flask session signing key | **Required in production** | `dev-nammapayana-secret-2026` (refuses to start in production with this value) |
| `DATABASE_PATH` | Path to SQLite database file | Optional | `instance/nammapayana.db` |
| `AI_PROVIDER` | AI backend (`gemini` / `none`) | Optional | `gemini` if `GEMINI_API_KEY` is set, otherwise `none` |
| `GEMINI_API_KEY` | Google Gemini API key for narrative enrichment and translation | Optional | _(empty — AI disabled)_ |
| `SUPABASE_URL` | Supabase project URL for Google OAuth | Optional | _(empty — OAuth disabled)_ |
| `SUPABASE_ANON_KEY` | Supabase anonymous/public key | Optional | _(empty)_ |
| `SUPABASE_PUBLISHABLE_KEY` | Supabase publishable key (frontend) | Optional | _(empty)_ |
| `SUPABASE_JWT_SECRET` | Supabase JWT secret for server-side token verification | Required if using Google OAuth | _(empty)_ |
| `RATE_LIMIT_TRANSLATE` | Flask-Limiter string for `/api/translate` | Optional | `10 per minute; 60 per hour` |
| `RATE_LIMIT_GENERATE` | Flask-Limiter string for `/api/trips/generate` | Optional | `20 per minute; 100 per hour` |
| `RATE_LIMIT_REPLAN` | Flask-Limiter string for `/api/trips/replan` | Optional | `30 per minute` |
| `ALLOWED_ORIGINS` | Comma-separated CORS origin allowlist | Optional | `http://localhost:5000,http://127.0.0.1:5000` |
| `WEB_CONCURRENCY` | Number of Gunicorn worker processes | Optional | `2` |
| `LOG_LEVEL` | Gunicorn log level (`info`, `debug`, `warning`, `error`) | Optional | `info` |
| `OSRM_BASE_URL` | Base URL of a self-hosted OSRM server for real road distances | Optional | _(empty — uses Haversine)_ |
| `ENABLE_DEMO_USER` | Seed a demo user in the DB (`1` to enable; development only) | Optional | `0` |

---

## Quick start (development)

```bash
git clone <repo>
cd nammapayana
cp .env.example .env
# Edit .env — at minimum set SECRET_KEY
pip install -r requirements.txt
python app.py
# Visit http://localhost:5000
```

No API keys are required for the core planner. Add `GEMINI_API_KEY` to enable narrative enrichment and richer Kannada translation.

---

## Running tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -q
python scripts/validate_data.py
```

119 tests are collected; 117 pass and 2 are skipped (Gemini-dependent tests skipped when `GEMINI_API_KEY` is not set).

---

## Production deployment

```bash
pip install -r requirements.txt
export FLASK_ENV=production
export SECRET_KEY=<strong-random-key>
gunicorn -c gunicorn.conf.py wsgi:app
```

The application will **refuse to start** in production if `SECRET_KEY` is left at the development default.

---

## Docker Deployment

```bash
# Build and run
docker compose up --build -d

# View logs
docker compose logs -f web

# Stop
docker compose down

# Backup database
docker compose exec web bash scripts/backup_db.sh /app/instance/backups
```

The container runs as a non-root user (`appuser`). The SQLite database is persisted in a named Docker volume (`db_data`). Set all secrets in `.env` before starting.

---

## Security model

- **JWT authentication**: Supabase JWTs verified server-side with `PyJWT` against `SUPABASE_JWT_SECRET`; `email_verified` claim enforced.
- **CSRF protection**: Flask-WTF token issued via `GET /api/csrf-token`; `@csrf_protect_if_enabled` on register, login, and logout endpoints.
- **Rate limiting**: Flask-Limiter (in-memory) — register: 3/min, login: 5/min, generate: 20/min, translate: 10/min.
- **Content Security Policy**: per-request nonce on `script-src`; `object-src 'none'`; `frame-ancestors 'none'`.
- **CORS**: explicit allowlist from `ALLOWED_ORIGINS`; no wildcard `*`.
- **WAL-mode SQLite**: journal mode set to WAL with foreign keys enabled; no shared cache.
- **Timing-constant login**: `hmac.compare_digest` for token comparisons; pre-computed dummy hash ensures missing-user and wrong-password branches take equal time.
- **No hardcoded secrets**: `config.py` reads all credentials from environment. Production guard raises `RuntimeError` if `SECRET_KEY` is the development default.
- **Session hardening**: `httpOnly`, `SameSite=Lax`, `Secure` (production), 24-hour lifetime, `session.clear()` on login/logout.

See `SECURITY_NOTES.md` for key rotation procedures.

---

## Data provenance policy

Every destination cost, distance, and entry fee has a `basis` field:

| Value | Meaning |
|---|---|
| `sourced` | Taken from an official source (ASI, forest department, KSTDC). `source_url` provided. |
| `estimated` | Reasonable approximation based on comparable sites. |
| `unknown` | Genuinely unverified — never fabricated. |

The engine never invents data. All source URLs are embedded in `data/destinations.json`.

Transit hubs, food places, and stay options are sourced from **OpenStreetMap** via the Overpass API and stored in `data/transit_hubs.json`, `data/food.json`, and `data/stays.json`. Attribution: © OpenStreetMap contributors, [ODbL 1.0](https://www.openstreetmap.org/copyright). Data is pre-fetched by `scripts/build_osm_data.py`; the app never calls Overpass at request time.

---

## API reference

| Method | Path | Auth Required | Description |
|--------|------|---------------|-------------|
| GET | `/` | No | SPA shell (index.html) |
| GET | `/api/health` | No | Service health check (DB status, routing provider, AI provider, destination count) |
| GET | `/api/destinations` | No | List destinations (filter by `region`, `category`, `max_hours`, `max_fee`) |
| GET | `/api/destinations/<id>` | No | Single destination detail |
| POST | `/api/trips/generate` | No | Generate a full itinerary from a JourneyDNA payload |
| POST | `/api/trips/validate` | No | Recompute budget and feasibility for an existing itinerary without full rebuild |
| POST | `/api/trips/replan` | No | Modify an existing trip via structured changes or natural language instruction |
| POST | `/api/trips/save` | No (session optional) | Persist a trip; returns `edit_token` for guest trips |
| GET | `/api/trips` | No (session optional) | List saved trips for current session or by `edit_token` |
| GET | `/api/trips/<id>` | No | Retrieve a saved trip by UUID |
| PUT | `/api/trips/<id>` | Edit token or owner | Update a saved trip |
| DELETE | `/api/trips/<id>` | Edit token or owner | Delete a saved trip |
| POST | `/api/trips/<id>/duplicate` | No | Duplicate a saved trip |
| POST | `/api/trips/<id>/share` | Edit token or owner | Get the read-only share token and URL |
| GET | `/api/shared/<share_token>` | No | Read-only public view of a shared trip |
| GET | `/api/trips/<id>/export` | No | Export trip as CSV (`?format=csv`), HTML, or PDF |
| GET | `/api/trips/<id>/export/ics` | No | Export trip itinerary as iCalendar (.ics) file |
| POST | `/api/trips/claim` | Session required | Claim guest trips by edit token after logging in |
| GET | `/api/phrases` | No | Kannada phrase lookup (filter by `q`, `scenario`) |
| POST | `/api/translate` | No | Translate text to Kannada (rate limited) |
| GET | `/api/csrf-token` | No | Issue a CSRF token for browser clients |
| POST | `/api/auth/register` | No | Register a new account (CSRF + rate limited) |
| POST | `/api/auth/login` | No | Local password login (CSRF + rate limited) |
| POST | `/api/auth/google-check` | Bearer JWT | Validate a Supabase Google OAuth token and establish a session |
| POST | `/api/auth/logout` | Session | Clear session (CSRF protected) |
| GET | `/api/auth/me` | Session | Return current user profile |

---

## Test count

**119 tests** collected (117 passed, 2 skipped). Run `python -m pytest tests/ -q` to verify.

---

## WCAG accessibility

Targeted accessibility improvements have been made (ARIA live regions, `role="main"`, `lang` attribute, `theme-color` meta). Full WCAG AA compliance requires manual testing with assistive technologies and an expert accessibility audit — this has not been performed.
