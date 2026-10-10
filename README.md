# Muselly

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

SQLAlchemy models `UserProfile` and `TasteProfile` store application
profile details and selected aesthetics in PostgreSQL. **Continue** saves
answers through the authenticated API; returning users can revisit and
edit their selections. The application uses the verified Supabase user
ID for every database query. It does not generate an AI Style DNA yet.

Alembic migration `0001_profiles` creates only `muselly_user_profiles`
and `muselly_taste_profiles`. It enables row-level security and revokes
browser Data API access to these tables. The Python API accesses them
through its private database connection. Supabase's `auth.users` schema
is not modified. User profile IDs mirror Supabase user IDs; account
removal should also remove the matching application profile.

```text
frontend/
  src/
    App.jsx                  # Landing, sign-in, and taste-test pages
    components/AuthProvider.jsx
    lib/supabase.js          # Supabase client and authenticated API requests
    styles/
  .env.example
backend/
  app/
    main.py                  # FastAPI routes and React build serving
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
collage are implemented. The extension, full image uploads, AI Style DNA,
and retailer integrations are still planned or illustrative.

## Product journey

```text
Landing page → Sign in → Taste test + inspiration images
            → Style DNA dashboard → Describe what to shop for
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
- **Shopping search:** a natural-language prompt and saved searches/results.

The user can update their preferences at any time; the profile evolves as they add or remove inspirations.

### 3. AI-powered product search

1. User asks: **“Find me a farewell dress under ₹3,000.”**
2. Muselly extracts the occasion, item category, budget, and other constraints.
3. User chooses supported retailers (for example, Amazon, Flipkart, Meesho, Myntra, AJIO, Urbanic, or Savana).
4. The shopping agent retrieves available candidate products from integrated product sources, then ranks them using visual fit, taste affinity, and user constraints.
5. Results appear as **product cards on the Muselly dashboard**: image, title, price, retailer, taste-match estimate, and **Why it matches** explanation.
6. Clicking **View product** opens the original retailer listing; Muselly does not handle checkout.

**Important:** Retailer support depends on lawful, reliable product-data access. The MVP should integrate one or two working sources first, not promise complete catalogs across every site.

### 4. Chrome extension

The extension uses the same signed-in profile and supports three actions while the user browses supported sites:

| Action | Behavior |
| --- | --- |
| **Find similar** | Analyze a selected outfit/product and show similar options in the extension panel or Muselly dashboard. |
| **Filter by my taste** | Score and highlight products visible on a supported retailer's results page; optionally dim weaker matches. |
| **Save to Muselly** | Save a selected image or product to the inspiration library for future recommendations. |

The extension is a **browsing companion**, not a separate shopping account. Page filtering requires site-specific support and does not search a retailer's entire inventory.

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
