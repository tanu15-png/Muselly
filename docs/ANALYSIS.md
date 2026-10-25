# Backend taste analysis

The [taste dashboard](DASHBOARD.md) displays saved analysis and offers explicit
generation/regeneration actions. Analysis also remains available through the
API and operator CLI; completing onboarding does not call Gemini automatically.
Qloo enrichment is a separate, explicit [dashboard/API flow](QLOO_ENRICHMENT.md).
Product search and shopping recommendations remain future work.

## Setup

Set these backend-only variables in `backend/.env`:

```env
GEMINI_API_KEY=your-private-key
GEMINI_MODEL=gemini-3.8-flash
```

The existing backend Supabase secret/service-role key must be able to read the
private inspiration bucket. No new dependencies or frontend variables are needed.
From `backend/`, apply `uv run alembic upgrade head` and restart Uvicorn.
Migration `0003_taste_analysis` adds `muselly_taste_analysis_runs`; RLS is enabled
and browser database-role access is revoked, as with the onboarding tables.

## HTTP endpoints

Both routes require the owner's Supabase access token as `Authorization: Bearer
<access_token>`. Neither accepts a user ID. An ordinary browser address-bar visit
without the header receives 401. Use Postman, curl, or the backend Swagger docs
at `http://localhost:8000/docs` (Authorize with the sign-in access token).
To find that token while signed in to Muselly, open browser developer tools →
Application/Storage → Local Storage for the Muselly site. In the Supabase
`sb-…-auth-token` entry, copy the `access_token` value. Paste that value into
Swagger's Authorize dialog; Swagger supplies the `Bearer` prefix. Then execute
GET `/api/onboarding/analysis` to view the saved result.

```bash
# Generate once; this waits for the result, usually within the 120-second model timeout.
curl -X POST http://localhost:8000/api/onboarding/analysis \
  -H "Authorization: Bearer $MUSELLY_ACCESS_TOKEN"

# Read the saved result without making another model call.
curl http://localhost:8000/api/onboarding/analysis \
  -H "Authorization: Bearer $MUSELLY_ACCESS_TOKEN"

# Explicitly regenerate matching inputs, incurring another model request.
curl -X POST 'http://localhost:8000/api/onboarding/analysis?force=true' \
  -H "Authorization: Bearer $MUSELLY_ACCESS_TOKEN"
```

POST validates required saved answers and 5–10 stored images. It downloads the
owner's private images, converts them to metadata-free JPEGs bounded to 1536px,
and sends their bytes plus human-readable questionnaire answers to Gemini.
Account email, account ID, credentials, and storage URLs are not sent. The
questionnaire can contain user-entered personal information; it is included
as requested context. The request uses the existing `httpx` dependency and
Google's `generateContent` REST API with a JSON Schema response contract.
The provider receives a simplified, expanded schema for compatibility; the
backend enforces the full Pydantic schema, length limits, and UUID references
after generation.

The response contains run ID, status, model, prompt version, source answers and
image metadata, token usage, timestamps, and `result`:

- `summary`: a concise overall interpretation.
- `images`: visible garments, colors, patterns, silhouettes, layering,
  accessories, possible aesthetics/materials, and uncertainties for each image.
- `recurring_visual_signals`: attributes with supporting image IDs.
- `questionnaire_interpretation`: how explicit preferences relate to the images.
- `conflicts`: question IDs, image evidence, and resolutions that respect the
  user's explicit preferences/dislikes.
- `limitations`: uncertainty and shortcomings of the analysis.

Responses are schema-validated, require every input image exactly once, and reject
unknown image/question references. These checks validate structure/provenance;
they do not guarantee the correctness of fashion interpretations. The prompt
does not infer demographics, size, or personality from people in pictures.
For a running or failed latest run, GET also includes an owner-scoped
`previous_successful` run when available, so regeneration failures do not hide
the user's saved insights. Its `stale` flag is computed against current inputs.

Identical successful inputs/model/prompt reuse a saved run. Changed answers or
replaced/removed images make old results `stale: true`; POST analyzes the latest
saved inputs. GET does not generate or refresh analysis. Historical runs retain
their input metadata and results until the account/taste test is deleted; they
do not retain additional image copies. No background regeneration is scheduled.

An in-progress run returns 409 to duplicate POSTs; GET exposes `status: running`.
The database lock is released before image/model calls so editing can continue.
A run abandoned by a process crash stops blocking retries after 15 minutes.
Quota/rate limits return 429; unavailable credentials/storage return 503;
invalid/blocked model responses return 502; model timeouts return 504. Failed runs
save a sanitized error and no fabricated result; another POST can retry. Existing
successful runs remain in the database if a later attempt fails.

## Server-operator run

For a specifically requested account, an operator who already has backend
database/storage credentials can run the same analysis service directly:

```bash
cd backend
uv run python -m app.analyze_saved --user-id OWNER_UUID \
  --output ../test-results/analysis/result.json
```

The CLI is not an HTTP authentication bypass. Exports contain private results;
the example output folder is ignored by Git. Read the result through the normal
authenticated GET route after running the CLI.

## Verification

`uv run pytest` covers migrated database schemas, real REST request construction
with mocked Gemini, authenticated owner isolation, minimum image/answer checks,
cached results, forced runs, stale detection, invalid output/evidence, provider
errors, retries, unavailable storage, and duplicate in-progress requests.
Live verification on 2026-10-10 analyzed 19 saved answers and five actual private
images using `gemini-3-flash-preview`. The newer 3.8/3.5 Flash endpoints returned
overload errors; the local backend `.env` now selects the available preview model.
The successful result is persisted in PostgreSQL, with a private ignored export
at `test-results/analysis/result.json`. Model availability can change; set
`GEMINI_MODEL` and restart the backend when switching models. See `todos.md` for
scope and acceptance notes. Mocked tests do not certify model interpretation quality.

References: [Gemini generateContent API](https://ai.google.dev/api/generate-content),
[structured outputs](https://ai.google.dev/gemini-api/docs/structured-output).
