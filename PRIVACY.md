# Privacy Policy

Last updated: 2025

Namma Payana is an open-source Karnataka travel planner. This document describes what data the application collects and stores when self-hosted or run locally.

## What is stored

| Data | Storage | Notes |
|------|---------|-------|
| Username | SQLite (plaintext) | Unique, required for account |
| Email address | SQLite (plaintext) | Used for login identifier |
| Display name | SQLite (plaintext) | Optional |
| Password | SQLite (bcrypt hash) | Plaintext never stored |
| Home city | SQLite (plaintext) | Optional preference |
| Travel persona | SQLite (plaintext) | Optional preference |
| Trip itineraries | SQLite (JSON) | Stored until deleted by user |
| Edit tokens | SQLite (SHA-256 hash) | Controls trip modification; plaintext never stored |

## What is NOT stored

- Passwords in plaintext
- Payment or financial information
- Precise GPS location data
- Browsing history or analytics
- Device identifiers
- IP addresses (rate limiter uses them in-memory only; not persisted)

## Data retention

- **Trip itineraries**: stored indefinitely until deleted by the user via `DELETE /api/trips/<id>`
- **User accounts**: stored until deleted; account deletion is not yet self-service (planned — raise an issue or contact the instance operator)

## Exporting your data

- **Trip export**: `GET /api/trips/<id>/export?format=csv` downloads cost data as CSV
- **ICS calendar**: `GET /api/trips/<id>/export/ics` downloads the itinerary as a calendar file
- **Full account export**: not yet implemented (planned)

## Deleting your data

- **Delete a trip**: `DELETE /api/trips/<id>` with `X-Edit-Token` header or logged-in session
- **Delete your account**: not yet self-service (planned). Contact the instance operator.

## Third-party services (all optional)

The application works without any third-party service. These are only used when explicitly configured:

| Service | Purpose | When used |
|---------|---------|----------|
| Google Gemini | Narrative enrichment, Kannada translation | Only when GEMINI_API_KEY is set |
| MyMemory API | Kannada translation fallback | Only when Gemini is not available |
| Supabase | Google OAuth login | Only when SUPABASE_* env vars are set |

When these services are used, the text or email you submit may be sent to them. Review their respective privacy policies.

## Self-hosted deployments

If you run a public instance of Namma Payana, you are responsible for your own privacy policy and compliance with applicable laws (GDPR, DPDP Act, etc.).
