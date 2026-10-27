# Contributing to Namma Payana

Thank you for your interest. This document covers how to contribute code, data, and documentation.

## Development setup

```bash
git clone <repo>
cd nammapayana
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
# Edit .env — at minimum set SECRET_KEY
```

## Running tests

```bash
# Full test suite
python -m pytest tests/ -q

# With coverage
python -m pytest tests/ --cov=. --cov-report=term-missing

# Data integrity
python scripts/validate_data.py
```

## Code standards

- **Formatting**: `black .` (line length 100)
- **Linting**: `ruff check .`
- **Type checking**: `mypy services/ --ignore-missing-imports`
- **No hardcoded secrets**: run `gitleaks detect` before committing

## Pull request checklist

- [ ] All existing tests pass (`python -m pytest tests/ -q`)
- [ ] New behaviour is covered by tests
- [ ] No new hardcoded secrets (run `gitleaks detect`)
- [ ] Data changes validated (`python scripts/validate_data.py`)
- [ ] CHANGELOG.md updated under `[Unreleased]`
- [ ] No float arithmetic in budget calculations (use `Decimal`)

## Adding a destination

Destinations live in `data/destinations.json`. Each entry must include:

```json
{
  "id": "snake_case_unique_id",
  "name_en": "English name",
  "name_kn": "ಕನ್ನಡ ಹೆಸರು",
  "region": "one of: Coastal Karnataka, Western Ghats, North Karnataka, Mysuru Region, Bengaluru Region, Central Karnataka",
  "category": "one of: nature, heritage, religious, wildlife, adventure",
  "lat": 12.3456,
  "lng": 76.7890,
  "visit_hours": 3.0,
  "entry_fee_inr": 50,
  "entry_fee_basis": "sourced",
  "best_season": ["Oct", "Nov", "Dec", "Jan", "Feb"],
  "description": "One concise paragraph.",
  "source_url": "https://official-source.gov.in/..."
}
```

**Basis values**:
- `sourced` — taken from an official source (ASI, forest department, KSTDC). Provide `source_url`.
- `estimated` — reasonable approximation based on similar sites. Document your reasoning in a PR comment.
- `unknown` — genuinely unverified. Use this rather than guessing.

Coordinates must fall within Karnataka bounds (lat 11.5–18.5, lng 74.0–78.6).
Run `python scripts/validate_data.py` before submitting.

## Dependency management

This project uses [pip-tools](https://pip-tools.readthedocs.io/) for dependency locking.
`requirements.in` and `requirements-dev.in` are the source-of-truth input files.

To regenerate the lockfile:
```
pip-compile requirements.in -o requirements.txt
pip-compile requirements-dev.in -o requirements-dev.txt
```

Do NOT run `pip-compile` in CI or on every install — only run it deliberately when updating dependencies.
