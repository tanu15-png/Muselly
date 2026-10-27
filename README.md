# Muselly

**Fashion discovery guided by your cultural taste.**

Muselly learns from a questionnaire, private reference images, Qloo cultural discoveries,
and the customer's own fashion notes. Its shopping agent searches a saved retailer catalog,
respects outfit requests and corrections, and links to real products. Shopping runs inside
the website at `/shop`; no extension is required.

## Technology stack

- **Frontend:** React and JavaScript, built with Vite.
- **Backend:** Python 3.12+ and FastAPI, served by Uvicorn.
- **Authentication:** Supabase Auth for email/password and Google sign-in.
- **Database:** Supabase PostgreSQL, accessed by Python using SQLAlchemy and psycopg.
- **Migrations:** Alembic manages the application tables. Supabase manages its authentication tables.

Node.js and npm are used only for React development and frontend builds.
The backend runs with Python; there is no Node.js backend.

## Setup

Follow [the setup guide](docs/SETUP.md) to create your Supabase project,
configure email and Google authentication, and fill in both `.env` files.

Run the Python backend from `backend/`:

```bash
cd backend
cp .env.example .env
# Fill in .env before migrating.
uv sync
uv run alembic upgrade head
uv run python tools/install_catalog.py
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Run the React frontend in another terminal:

```bash
cd frontend
cp .env.example .env
# Fill in .env with the same Supabase project's URL and publishable key.
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to the Python backend at
`http://127.0.0.1:8000`. API docs are at `http://127.0.0.1:8000/docs`;
`GET /api/health` reports whether the API is running.

To serve the built React app through Python, run `npm run build` from
`frontend/`, set `APP_ORIGIN=http://localhost:8000` in `backend/.env`, add
`http://localhost:8000/auth/callback` to Supabase's redirect allow list,
and start Uvicorn. Frontend environment variables are compiled into the
build; rebuild after changing them.

## Sign-in and taste test

The landing page has a **Sign in** link and a **Get started** action, both
leading to `/sign-in`. The sign-in card offers email/password, email
account creation, and Google authentication below the headline. After
Python verifies the Supabase session, the card shows one **Start taste
test** action for returning email users. New registrations and Google/email
confirmation callbacks continue directly to the taste test after verification.
Visiting `/taste-test` while signed out returns to sign-in.

Email registration without an immediate session shows a confirmation/resend
screen. Opening the newest email link in the same browser signs the user in
and opens the taste test, without asking for another password. Supabase's
default email service restricts recipients; see the setup guide for custom SMTP.

The React app uses Supabase's PKCE flow and manages session refresh.
The Python API independently checks access tokens with Supabase before
returning or saving any taste-test data. Passwords and Google credentials
are managed by Supabase, not application tables or a local account file.

The taste test has five guided stages and twenty questions, including optional
current city/region and country. Choices, custom Other answers, names, and
location autosave through `/api/onboarding`; Back/Continue also save the
current position. Completed users see their taste dashboard at `/dashboard`,
with their original preferences, private inspiration gallery, and actual Gemini
insights. Evidence links connect interpretations to their source images.
Users can edit preferences, manage inspirations, and explicitly generate or
regenerate analysis. Loading the dashboard never triggers a model request.
See [dashboard behavior](docs/DASHBOARD.md) and
[analysis endpoints and setup](docs/ANALYSIS.md).

The final stage requires **5–10 inspiration images** (JPG/JPEG, PNG, WebP;
10 MB per file). It supports browsing, drag-and-drop, progress, retry, removal,
and replacement. FastAPI verifies image contents with Pillow and strips
embedded metadata before storing them in a private Supabase Storage bucket.
Image downloads go through authenticated, owner-scoped API endpoints; temporary
browser preview URLs are never stored as image references.

Alembic `0002_taste_test` adds `muselly_taste_tests` and
`muselly_inspiration_images`, with RLS enabled and browser Data API access
revoked. It also creates the private `muselly-inspirations` bucket in Supabase.
The existing profile tables and legacy aesthetics endpoint remain intact.
All application queries use the verified Supabase user ID. Supabase's
`auth.users` schema is not modified.

**Upload setup:** add `SUPABASE_SECRET_KEY` to `backend/.env` only,
then restart the backend. Use the secret key (`sb_secret_...`) from your project's API key settings.
The legacy `SUPABASE_SERVICE_ROLE_KEY` is also supported. Never put it in a `VITE_` variable. No frontend
environment changes are needed. Run `uv sync` and `uv run alembic upgrade head`
from `backend/`. See [setup](docs/SETUP.md) and
[implementation and verification notes](docs/TASTE_TEST.md).

```text
frontend/
  src/
    App.jsx                  # Landing and protected page routing
    components/TasteTest.jsx  # Guided questionnaire and saved edits
    components/TasteDashboard.jsx # Saved preferences, Gemini insights, inspirations
    components/InspirationUploader.jsx # Private upload gallery
    components/AuthProvider.jsx
    lib/supabase.js          # Supabase client and authenticated API requests
    styles/
  .env.example
backend/
  app/
    main.py                  # FastAPI routes and React build serving
    onboarding.py            # Draft validation, private uploads, completion
    auth.py                  # Supabase access-token verification
    models.py                # SQLAlchemy user and taste profiles
    database.py              # SQLAlchemy engine and sessions
    config.py                # Environment configuration
  alembic/                   # Database migrations
  tests/
  pyproject.toml
  uv.lock
  .env.example
```

Check the implementation with:

```bash
# From backend/
uv run pytest

# From frontend/
npm test
npm run build
```

Live Google sign-in, confirmation emails, and PostgreSQL connections
require your configured Supabase project. Automated backend tests use a
mocked Supabase service and a temporary SQLite database.

## Customer journey

1. Sign in and answer the twenty-question taste test.
2. Upload 5–10 private reference images for color, pattern and clothing analysis.
3. Explore Qloo discoveries across music, films, shows and books. Feedback saves locally,
   advances instantly and syncs in the background; analytics waits for pending choices.
4. Save a discovery as fashion inspiration and explain its relevance in a short autosaved note.
5. Visit `/shop` and describe an outfit, for example “Everyday office outfit under ₹2,000.”
6. Correct the agent (“Less formal, more floral”), save likes/dislikes and open a retailer link.

Qloo supplies cultural connections and brand affinities. Gemini interprets language and reference
images. The ranking layer respects explicit constraints and corrections before personalization.
A cultural entity name or poster color alone does not establish a clothing preference.

## Saved retailer catalog

The bundled snapshot contains validated women's products from Myntra, AJIO, Nykaa Fashion and
H&M India. SHEIN India did not pass the source checks and is excluded. Product collection is an
offline preparation step: customer searches and ordinary tests never call Apify.

Run `uv run python tools/install_catalog.py` from `backend/` after cloning to install the bundled
snapshot. It uses no API key or network. The archive excludes account details, tokens and raw
collection logs. `MYNTRA_CATALOG_PATH` remains available as a backwards-compatible override;
its default now points to `backend/data/multi-retailer/catalog-products.json`.

Images are retailer-hosted URLs. Prices and observed size availability are collection-time
snapshots; customers confirm current details at the store. Exact source IDs and canonical URLs
are deduplicated. Cross-store offers remain separate when equivalence cannot be verified.

See [catalog preparation and limitations](docs/CATALOG.md), [shopping agent behavior](docs/SHOPPING_AGENT.md)
and the [three-minute hackathon demo](docs/HACKATHON_DEMO.md).

## Deploy on Railway

The root Dockerfile builds the website and API together and installs the saved
catalog without scraping. See the [Railway deployment guide](docs/RAILWAY.md)
for service variables, database migrations and production sign-in redirects.
