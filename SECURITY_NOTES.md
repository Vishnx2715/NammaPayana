# SECURITY_NOTES.md

## Immediate Actions Required

### 1. Revoke the Exposed Gemini API Key
1. Go to https://aistudio.google.com/apikey
2. Find the key starting with `AQ.Ab8RN6IUF...` and delete/revoke it immediately.
3. Generate a new key and set it in your `.env` file as `GEMINI_API_KEY=<new_key>`.

### 2. Rotate Supabase Keys
1. Go to your Supabase project dashboard > Settings > API.
2. Rotate the `anon` key and the `service_role` key.
3. Update your `.env` file with the new values.
4. Ensure Row Level Security (RLS) is enabled on ALL tables in your Supabase project.
   Without RLS, the anon key grants full table access.

## Purge Secrets from Git History

The exposed keys exist in git history and must be purged even after code changes.

### Using git-filter-repo (recommended)
```bash
pip install git-filter-repo
# Create a replacements file:
cat > replacements.txt <<EOF
<YOUR_LEAKED_GEMINI_KEY_HERE>==>REDACTED_GEMINI_KEY
REDACTED_SUPABASE_HOST==>REDACTED_SUPABASE_HOST
REDACTED_SUPABASE_PUB1==>REDACTED_SUPABASE_PUB
REDACTED_SUPABASE_PUB2==>REDACTED_SUPABASE_PUB
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIs==>REDACTED_SUPABASE_JWT
EOF
git filter-repo --replace-text replacements.txt
git push --force-with-lease origin main
```
After pushing, all collaborators must re-clone the repository.

## Gitleaks Setup
Install gitleaks and run before every commit:
```bash
gitleaks detect --source . --config .gitleaks.toml
```

## Row Level Security Checklist
- [ ] Enable RLS on `users` table
- [ ] Enable RLS on `trips` table (if using Supabase for storage)
- [ ] Add policies: authenticated users can only read/write their own rows
- [ ] Test with the anon key that direct table reads are blocked

## Pre-commit Hook Setup
```bash
pip install pre-commit
pre-commit install
```
Once installed, `gitleaks` runs automatically on every `git commit` and blocks commits containing secrets.

## CSRF Exemption Table

| Route | Method | Auth type | CSRF protected? | Reason |
|-------|--------|-----------|-----------------|--------|
| /api/trips/save | POST | session cookie | YES | State change on session-identified resource |
| /api/trips/<id> | PUT | session cookie OR edit_token | YES | State change; session path requires protection |
| /api/trips/<id> | DELETE | session cookie OR edit_token | YES | Destructive state change |
| /api/trips/claim | POST | session cookie (required) | YES | Transfers ownership via session identity |
| /api/trips/<id>/share | POST | session cookie OR edit_token | YES | Returns share token; session path needs protection |
| /api/auth/login | POST | credentials | YES | Session creation |
| /api/auth/logout | POST | session cookie | YES | Session destruction |
| /api/auth/register | POST | credentials | YES | Account + session creation |
| /api/trips/generate | POST | none | NO (exempt) | Pure computation, no session, no state change |
| /api/trips/replan | POST | none | NO (exempt) | Pure computation, no session, no state change |
| /api/trips/validate | POST | none | NO (exempt) | Read-only validation, no state change |
| /api/translate | POST | none | NO (exempt) | Stateless translation, no session dependency |
| /api/auth/google-check | POST | Bearer JWT (Supabase) | NO (exempt) | Verified via Bearer JWT, not session cookie. Distinguishing NOT_REGISTERED from INVALID is intentional in the Google OAuth flow — the user chose Google, so a 'not registered' response directs them to register, not an enumeration attack. |
