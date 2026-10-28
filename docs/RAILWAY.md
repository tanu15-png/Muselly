# Deploy Muselly on Railway

One Docker service serves the built React website and FastAPI API on the same
domain. The image includes the saved **6,098-product catalog**. Deployment and
shopping searches do not call Apify. Authentication, database and private images
continue to use your existing Supabase project; no Railway volume is required.

## Update the existing deployment: outfit previews

1. Open the existing Muselly service in Railway, then **Variables**.
2. Keep the existing Gemini key, Qloo and Supabase variables. Add
   `GEMINI_IMAGE_MODEL=gemini-nano-banana-2.1` (the tested default).
3. Deploy the latest `main` commit from GitHub. If automatic deployment is enabled,
   the push can start a build immediately; otherwise use **Deploy Latest Commit**.
4. Keep the root Dockerfile and `alembic upgrade head` pre-deploy command. Migration
   `0012_outfits` is already applied to the current Supabase database; Alembic will
   skip it there and apply it on any other configured database.
5. Wait for build, migration and health checks to pass. Open `/shop`, sign in,
   and reload to see saved previews. Check Like / Not for me, optional reason,
   image correction and Find similar pieces. Each generated image or correction
   uses one allowance: 3 daily (midnight UTC), 10 lifetime per account. Feedback
   and product searches do not use image allowances.

Generated previews and their feedback are private, stored in Supabase PostgreSQL,
so no new Storage bucket or Railway volume is required. All existing catalog
products remain bundled. No new API key or frontend VITE variable is needed.
The previous live test saved two previews on the selected review account.

## 1. Push the project

Push the project to your GitHub repository, including `Dockerfile`, `.dockerignore`,
`railway.json`, `backend/start.py`, both dependency lockfiles, application sources,
`shared/` and **`assets/catalog/muselly-catalog.zip`**. The ignored `backend/data/`
directory is unnecessary: the Docker build installs the bundled archive and
checks its checksums. Keep your `.env` files out of GitHub.

## 2. Create one Railway service

In Railway choose **New Project â†’ Deploy from GitHub repo**, then select Muselly.
Keep the service root at the repository root, not `backend/` or `frontend/`.
Railway reads the root Dockerfile and `railway.json`. Leave custom build and
start commands unset. An initial build without variables may fail; add the
variables below and deploy again.

## 3. Add service variables

Copy these values from your existing local configuration into the service's
**Variables** section. Do not upload your `.env` file to the repository.

```dotenv
# Public values: required during the frontend build
VITE_SUPABASE_URL=https://YOUR-PROJECT.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=YOUR-PUBLIC-PUBLISHABLE-KEY

# Backend configuration: same Supabase project as above
SUPABASE_URL=https://YOUR-PROJECT.supabase.co
SUPABASE_PUBLISHABLE_KEY=YOUR-PUBLIC-PUBLISHABLE-KEY
SUPABASE_SECRET_KEY=YOUR-BACKEND-ONLY-SECRET-KEY
DATABASE_URL=postgresql+psycopg://USER:ENCODED-PASSWORD@SESSION-POOLER-HOST:5432/postgres?sslmode=require
APP_ORIGIN=https://YOUR-RAILWAY-DOMAIN
GEMINI_API_KEY=YOUR-EXISTING-KEY
GEMINI_MODEL=YOUR-CURRENT-WORKING-MODEL
QLOO_API_KEY=YOUR-EXISTING-KEY
QLOO_BASE_URL=https://api.qloo.com
```

Use your account's existing Qloo host if different. If you use a legacy Supabase
service-role key, set `SUPABASE_SERVICE_ROLE_KEY` instead of `SUPABASE_SECRET_KEY`.
Use Supabase's session-pooler connection for IPv4 connectivity; retain the
`postgresql+psycopg` scheme and URL-encode special characters in the password.

Only the two `VITE_` variables are embedded in the browser bundle. Keep Gemini,
Qloo, database and Supabase secret/service-role credentials in backend variables.
Changing a `VITE_` value requires rebuilding the deployment.

Leave `MYNTRA_CATALOG_PATH` unset so the included multi-retailer snapshot is used.
No Apify token is needed. Railway supplies `PORT`; the server binds to it on
`0.0.0.0` automatically. Before serving traffic, Railway runs `alembic upgrade head`
against your configured database; failed migrations stop the deployment.

## 4. Set the domain and Google sign-in redirect

Under service **Settings â†’ Networking**, generate a public domain. Set
`APP_ORIGIN` to its full HTTPS origin, without a trailing slash, and redeploy.
If Railway asks for the target port, use its assigned `PORT` (8080 by default).

In **Supabase â†’ Authentication â†’ URL Configuration**:

- Set **Site URL** to the public HTTPS origin.
- Add `https://YOUR-RAILWAY-DOMAIN/auth/callback` to **Redirect URLs**.
- Keep your localhost callback allowlisted if you still develop locally.

Google's provider callback remains the Supabase callback configured for your
project. The Railway URL above is where Supabase sends the user afterwards.

## 5. Review the deployment

Open `/api/health` and expect `{"status":"ok"}`. Then test Google sign-in,
questionnaire, an inspiration upload, cultural discoveries, saved feedback,
analytics and a shopping request. Reload `/shop` directly to check routing.
Confirm product images and retailer links work. Health checks confirm the server
is running; they do not prove external services or database permissions work.

The catalog is a fixed snapshot. Redeployments reinstall it without scraping;
likes, notes and profiles remain in Supabase. Confirm live prices and availability
on the retailer's website.

## Optional local Docker check

With Docker Desktop running, build from the repository root using your **public**
Supabase values:

```sh
docker build --build-arg VITE_SUPABASE_URL=https://YOUR-PROJECT.supabase.co --build-arg VITE_SUPABASE_PUBLISHABLE_KEY=YOUR-PUBLIC-KEY -t muselly .
docker run --rm -p 8080:8080 --env-file backend/.env -e APP_ORIGIN=http://localhost:8080 muselly
```

Open `http://localhost:8080`. This local command starts the server; migrations are
Railway's separate pre-deploy step. Do not pass a Windows catalog-path override
into the Linux container.

## Troubleshooting

- **Frontend build fails:** provide both public `VITE_` variables and rebuild.
- **Migration fails:** check the database URL, password encoding and Supabase
  connectivity in deployment logs.
- **Google returns to localhost:** update Supabase Site URL, redirect allowlist
  and `APP_ORIGIN`, then redeploy.
- **Catalog missing:** verify the archive is committed and the build log reports
  installation of 6,098 products.

References: [Railway Dockerfiles](https://docs.railway.com/builds/dockerfiles),
[Railway configuration schema](https://railway.com/railway.schema.json),
[Supabase redirect URLs](https://supabase.com/docs/guides/auth/redirect-urls).
