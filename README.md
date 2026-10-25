# Muselly

> **Current product direction:** Use the website for the taste test, Style DNA,
> private inspirations, Qloo brand exploration, and saved finds. Product search,
> Qloo discovery, personalized ranking, corrections, and saving live in the downloadable
> Chrome/Edge extension. **Get Extension** downloads its ZIP; follow the
> [installation and feature guide](docs/EXTENSION.md) to load it unpacked.


**Your taste, everywhere you shop.**

Muselly is an AI-powered fashion discovery platform that learns a user's style from a visual taste test and inspiration images, then helps them find matching products across supported shopping sites. A companion Chrome extension brings that taste profile into everyday browsing.

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

**Other features:** the responsive landing page, navigation, FAQs, and
collage are implemented, along with the taste questionnaire, private inspiration
uploads, Gemini analysis, taste dashboard, and explicit Qloo brand enrichment.
Qloo needs a backend API key and migration `0004_qloo_enrichment`; see the
[enrichment guide](docs/QLOO_ENRICHMENT.md). Product search, loaded-page ranking,
Qloo discovery, product corrections, save-only snapshots, and saving are implemented in the
[downloadable Chrome/Edge extension](docs/EXTENSION.md). The website's discovery
page shows Qloo brands and saved product bookmarks.


## Product journey

```text
Landing page → Sign in → Taste test + inspiration images
            → Style DNA dashboard → Discovery page (/explore)
            → Describe what to shop for
            → Choose retailers → Personalized product results
            → Open product on retailer's website

Chrome extension ↔ Saved Style DNA + inspiration library
```

### 1. Landing page and onboarding

The landing page introduces Muselly with **“Discover fashion that feels like you.”** Its navigation includes **How it works · For you · Extension · FAQs**, plus a **Sign in** action. The hero’s **Get started** button opens sign-in; the taste-test option appears after authentication. The Extension section includes a **Get Extension** button.

After signing in, users complete a short visual taste test (preferred outfits, aesthetics, colors, silhouettes, and dislikes). They can also upload photos, screenshots, or Pinterest inspirations. Connecting a Pinterest account/board is a *future enhancement*, subject to API access and permissions; the MVP supports manual uploads and saving individual images through the extension.

### 2. Style DNA dashboard

Muselly analyzes the selected images and answers to generate an editable **Style DNA** profile:

- **Taste overview:** aesthetics, colors, silhouettes, materials, and preferred brands.
- **Taste graph:** visual connections between saved inspirations and supported style/brand affinities.
- **Inspiration library:** uploaded and saved images, with options to remove or organize them.
- **Taste analyzer:** explanations of recurring preferences and why suggested items fit.
- **Discovery page:** `/explore` contains Qloo brand discovery, a natural-language search prompt, editable filters, and current product results. The home-page search before “How it works” opens it. Saving searches/products remains future work.

The user can update their preferences at any time; the profile evolves as they add or remove inspirations.

### 3. Product search in the extension

Write a prompt such as **midi dress under 2000** in the extension side panel,
open a retailer, and rank the loaded products against your saved taste and Qloo
brand affinities. Results, prices, grounded explanations, and product links appear
in the panel. Product prompts and cards are no longer mounted on the website.

### 4. Chrome / Edge extension

**Get Extension** downloads a Manifest V3 ZIP from `/api/extension/download`.
Extract it, enable Developer mode at `chrome://extensions`, choose **Load
unpacked**, pin Muselly, and connect your signed-in account from its side panel.
The installation page is `/extension`; this is not a published store listing.

- **Search and rank:** prompt-based retailer links and personalized ranking of loaded products.
- **Take snapshot:** visible-tab capture, preview, and crop; image upload is also supported.
- **Discover my style:** Qloo-led brand discovery, personalized page ranking, and persistent product corrections. Snapshots only save inspirations.
- **Save to Muselly:** private product bookmarks in Saved finds, or snapshot uploads to the inspiration library.

See [setup, permissions, API, verification, and practical limits](docs/EXTENSION.md).
Retailer page layouts can change; stock and sizes need confirmation at the store.

### 5. AI and Qloo responsibilities

```text
Taste test + images ──→ Vision model ──→ Visual style attributes
                                            │
Supported brands/interests ──→ Qloo API ──→ Taste/brand affinities
                                            │
Shopping request ──→ Agent + product source ──→ Candidate products
                                            │
                          Ranking + explanations ──→ Recommendations
```

- **Vision model:** interprets images and extracts visible fashion attributes.
- **Qloo:** enriches supported entities and cultural/brand taste affinities; it does **not** directly recognize uploaded images or provide retail inventory.
- **Shopping agent:** interprets requests, chooses tools, retrieves products, and applies constraints.
- **Ranking layer:** combines visual similarity, Qloo-derived signals where available, and budget/occasion fit. Any displayed match percentage is Muselly's own estimated score, not an official Qloo score.

## Hackathon MVP scope

**Build now:** responsive landing page; authentication; visual taste test; image upload; Style DNA dashboard; natural-language search; one or two real product sources; ranked results with retailer links; basic Chrome extension for saving images and analyzing/filtering supported pages.

**Later:** full Pinterest account sync, broader retailer integrations, richer taste graph, collaborative shopping, outfit building, and more advanced personalization.

## Success criterion

A new user can **sign in → create their taste profile → search for an occasion-based outfit → compare personalized matches → open a retailer product**, then use the extension to save or evaluate another look without starting over.
