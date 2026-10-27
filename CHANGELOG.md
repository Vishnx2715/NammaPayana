# Changelog

All notable changes to Namma Payana are documented here.
Format: [Unreleased] / [version] — date, with Added/Fixed/Security/Changed sections.

## [Unreleased]

### Security
- Removed hardcoded Gemini API key and Supabase credentials from source (Phase 0)
- Fixed 10 authentication vulnerabilities: account takeover, UUID-as-password, demo user in production, account enumeration, no brute-force protection, weak passwords, missing session hardening, no CSRF, sensitive localStorage data, user_store code quality (Phase 0B)
- Added trip ownership enforcement and /api/trips/claim endpoint (Phase 1)
- Eliminated XSS sinks in app.js, auth.js, map.js, phrases.js with escapeHtml() and JSON.stringify for onclick handlers (Phase 2)
- CSP with per-request nonces, CORS allowlist, HSTS in production, removed X-XSS-Protection (Phase 1)

### Fixed
- Wheelchair accessibility filter operator-precedence bug (Phase 3)
- Long trips now produce explicit rest days instead of silent empty days (Phase 3)

### Added
- 52 destinations (up from 24), balanced across all Karnataka regions (Phase 4)
- Data validation script: scripts/validate_data.py (Phase 4)
- RoutingProvider abstraction: HaversineProvider (default) and OSRMProvider with fallback (Phase 5)
- Ghat road and monsoon travel time multipliers (Phase 5)
- Season scoring and monsoon warnings from best_season + start_date (Phase 3)
- Shared SQLite helper with WAL mode and foreign keys (Phase 6)
- JSON structured logging with per-request IDs (Phase 6)
- pyproject.toml, requirements-dev.txt (Phase 6)
- Read-only share links and ICS calendar export (Phase 7)
- Safety info on 5 high-risk destinations (Phase 7)
- WCAG accessibility improvements: aria-live, role="main", theme-color (Phase 7)

### Infrastructure
- Multi-stage non-root Dockerfile (Phase 16)
- docker-compose.yml with persistent volume and health check (Phase 16)
- SQLite backup script (scripts/backup_db.sh) (Phase 16)
- OSM transit/food/stays pipeline (scripts/build_osm_data.py) (Phase 13)
- GitHub Actions CI with ruff, mypy, bandit, pytest coverage, gitleaks (Phase 9)
