# React, Python, and Supabase setup

## Current project

The project's [Supabase dashboard](https://supabase.com/dashboard/project/kvlyrfrbyqfqjwsniaqf)
already exists. Its API URL is `https://kvlyrfrbyqfqjwsniaqf.supabase.co`.
The local `frontend/.env` and `backend/.env` are configured and ignored by
Git; credentials are not included in this guide. Alembic revisions
`0001_profiles` and `0002_taste_test` have been applied to this project’s PostgreSQL database.

Open [Authentication providers](https://supabase.com/dashboard/project/kvlyrfrbyqfqjwsniaqf/auth/providers)
to configure Email and Google. Set the Site URL to
`http://localhost:5173` and allow `http://localhost:5173/auth/callback`
under Authentication → URL Configuration.

For the Google OAuth Web application, use:

- Authorized JavaScript origin: `http://localhost:5173`
- Authorized redirect URI: `https://kvlyrfrbyqfqjwsniaqf.supabase.co/auth/v1/callback`

Save the Google client ID and client secret in Supabase's Google provider
settings. They do not belong in the React environment file.

## 1. Install local tools

Use Python 3.12 or newer and [uv](https://docs.astral.sh/uv/getting-started/installation/)
for the Python backend. Use Node.js 22.12 or newer and npm for the React/Vite
frontend. Node.js does not run the backend.

## 2. Create a Supabase project

Create a project in [Supabase](https://supabase.com/dashboard), choose a
database password, and wait for provisioning. Save the project URL and
**publishable key** from the project's API settings or Connect panel.
The same project URL and publishable key go in the frontend and backend
environment files. A legacy `anon` key also works if your project still
uses legacy keys. Do not use a secret or `service_role` key in Vite.

## 3. Configure email and Google authentication

In Supabase Authentication:

1. Enable the Email provider with password sign-in. Keep email confirmation
   enabled. New users see a dedicated confirmation screen with a resend
   option; opening the email link in the same browser signs them in and
   opens the taste test automatically.
2. Set the Site URL to `http://localhost:5173` during development.
3. Add `http://localhost:5173/auth/callback` to the allowed Redirect URLs.
   Add your final site's `/auth/callback` URL when deploying. If you serve
   the React build from Python locally, also add
   `http://localhost:8000/auth/callback`.
4. Enable the Google provider. Create a Google OAuth **Web application**
   client in Google Cloud. Add `http://localhost:5173` under Authorized
   JavaScript origins. Configure the consent screen and add test users
   if the Google application is in testing mode. Register the callback
   displayed by Supabase, normally
   `https://YOUR_PROJECT.supabase.co/auth/v1/callback`, as Google's
   authorized redirect URI. Enter the Google client ID and client secret
   in the Supabase Google provider settings.

Google returns to Supabase's callback; Supabase then returns to the app's
`/auth/callback`. These are two different redirect URLs.

For email confirmations, complete sign-up in the same browser/device where
you started, because the PKCE verifier is stored there. Configure custom
SMTP in Supabase before using confirmation emails with your own users;
the default mail service only sends to your Supabase organization’s team
addresses and has strict testing limits.

References: [Google provider setup](https://supabase.com/docs/guides/auth/social-login/auth-google),
[redirect URLs](https://supabase.com/docs/guides/auth/redirect-urls),
[email/password auth](https://supabase.com/docs/guides/auth/passwords),
[PKCE](https://supabase.com/docs/guides/auth/sessions/pkce-flow), and
[SMTP](https://supabase.com/docs/guides/auth/auth-smtp).

## 4. Configure the React frontend

Copy `frontend/.env.example` to `frontend/.env`:

```dotenv
VITE_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY
```

These are public configuration values. Restart Vite after changing them.

## 5. Configure the Python backend and database

Copy `backend/.env.example` to `backend/.env`:

```dotenv
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY
DATABASE_URL=postgresql+psycopg://YOUR_DB_USER:YOUR_ENCODED_PASSWORD@YOUR_DB_HOST:5432/postgres?sslmode=require
APP_ORIGIN=http://localhost:5173
SUPABASE_SECRET_KEY=YOUR_BACKEND_ONLY_SECRET_KEY
```

Use the **Direct connection** or **Session pooler** connection from
Supabase's Connect panel. The Session pooler is useful when your network
does not support the direct connection's IPv6 address. Preserve the
username, host, database, and port from the copied URL; change its scheme
from `postgresql://` to `postgresql+psycopg://`. URL-encode special
characters in the database password and use `sslmode=require`.
The Python API and Alembic use this private connection. Never place
`DATABASE_URL` or your database password in the frontend environment.

Use the project's database owner connection for the initial migration
and local development. A custom runtime role must have permission to
access the application tables and operate with their RLS configuration;
this implementation does not set PostgREST JWT claims on SQL connections.

Reference: [Supabase PostgreSQL connections](https://supabase.com/docs/guides/database/connecting-to-postgres).

## 6. Install, migrate, and run

From `backend/`:

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Alembic creates the application profile/taste tables and secures their
Data API access. Revision `0002_taste_test` adds questionnaire drafts and
inspiration image metadata, and creates `muselly-inspirations` as a private
Supabase Storage bucket (10 MB per object; JPEG, PNG, WebP). It does not alter
Supabase authentication tables. The existing profile/aesthetic data is retained.

Set `SUPABASE_SECRET_KEY` in **backend/.env only** to the secret key
(`sb_secret_...`) from Supabase Project Settings → API keys. A legacy
service_role JWT can instead be supplied as `SUPABASE_SERVICE_ROLE_KEY`. Upload, read, and
delete operations use this backend credential after checking the signed-in
user's ownership. Keep the bucket private and do not add browser access
policies. This follows Supabase's [private bucket access model](https://supabase.com/docs/guides/storage/buckets/fundamentals).
No additional frontend variables are required. Restart Python after changing
its environment. Without the key, questionnaire saving works but uploads show
a recoverable storage-configuration error.

For a PostgreSQL installation without the Supabase Storage schema, the migration
creates only application tables. Create the private bucket in your Supabase
Storage project before using uploads.

From `frontend/`, in another terminal:

```bash
npm install
npm run dev
```

Open the local URL printed by Vite (normally `http://localhost:5173`).
If that port is busy, Vite uses the next available port. Add the callback
URL for the port you use to Supabase's allowed Redirect URLs, for example
`http://localhost:5174/auth/callback`. Browser sessions are separate for
each port, so start sign-in and open the confirmation link on the same
port and browser. For an already confirmed account, sign in with its
password on the port you are using.

The frontend sends `/api` requests through
Vite to Python on port 8000. Use the exact same origin you configured
in Supabase and `APP_ORIGIN`.

## 7. Check the user flow

1. Select **Get started** or **Sign in** on the landing page.
2. Create an email account and open its confirmation link in the same
   browser, or use Google sign-in. Both callbacks go directly to the taste
   test after the Python API verifies the session; no second sign-in is
   needed. If Supabase returns a session immediately at registration, the
   app also opens the taste test automatically.
3. Existing users who sign in with email can select **Start taste test**.
4. Complete the five stages. Optional age, size, location, and cultural
   inspiration questions can be skipped. Other answers reveal a text field;
   the aesthetic and shopping-personality questions allow at most three choices.
5. Refresh during the quiz after “Progress saved” and check that the answers
   and current question return. Back must preserve choices.
6. Add 5–10 valid images. Test retry, replacement, removal, invalid files,
   oversized files, and the ten-image cap. Fewer than five must block finishing.
7. Finish and check the saved `/dashboard` placeholder. Revisit `/taste-test`
   to edit; existing answers and images must return. No analysis runs.
8. Sign out and test `/taste-test` and `/dashboard`: both must return to
   `/sign-in`. With two accounts, verify that neither can fetch, replace, or
   remove the other's image IDs through the API.

Run `uv run pytest` in `backend/`, and `npm test` plus `npm run build`
in `frontend/` for local checks. Supabase credentials are not needed for the automated tests.

## Future model changes

Update `backend/app/models.py`, then run from `backend/`:

```bash
uv run alembic revision --autogenerate -m "describe the model change"
```

Review the generated migration, including RLS/grants for any new public
tables, then apply it with `uv run alembic upgrade head`. Autogeneration
is scoped to Muselly's models so unrelated Supabase tables are not dropped.
Back up real user data before applying destructive schema changes.

## Confirmation email not arriving

If you use Supabase's default email service, confirmation delivery is
restricted to your Supabase organization's team addresses and subject to
strict email rate limits. A successful signup response does not prove
inbox delivery. Check Authentication logs for provider/send errors and
check the inbox spam folder.

For other recipients, open Authentication → Email → SMTP Settings
(the Dashboard also links to Custom SMTP from authentication settings).
Enable custom SMTP and enter your mail provider's SMTP host, port,
username, password, sender email, and sender name. Follow your provider's
domain/sender verification requirements before sending. Save the settings,
then use **Resend confirmation email** on the app's confirmation screen.
Always open the newest link in the same browser where the request started.

The app waits 60 seconds between resend attempts and reports errors. After
confirmation, Supabase creates the session and Python verifies it; the app
opens `/taste-test` without another sign-in. Existing unconfirmed users
who try email sign-in are shown the confirmation/resend screen as well.

See [Supabase SMTP documentation](https://supabase.com/docs/guides/auth/auth-smtp).
