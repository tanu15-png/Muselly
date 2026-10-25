> The active dashboard now uses Qloo cultural discoveries. See [Cultural discovery](CULTURAL_DISCOVERY.md). The notes below describe the earlier visual-analysis dashboard and its reusable analytics components.

# Taste dashboard

`/dashboard` now displays the authenticated owner's saved questionnaire,
inspiration images, and actual Gemini analysis. It uses the existing AuthProvider,
FastAPI endpoints, private Storage reads, shared question definitions, and Muselly
design tokens. Product search and Qloo brand discovery now live on the separate
`/explore` page, accessible from the dashboard and the home-page search section.

## Behavior

- Loading the page reads `GET /api/onboarding` and `GET /api/onboarding/analysis`.
  It never automatically makes a paid model request.
- Completed users can read their style summary, interpreted aesthetics, fits,
  styling details, and approximate named color swatches. Counts and evidence
  links come from the actual image observations; no match percentages are invented.
- Source labels distinguish AI interpretations from the user's stated answers.
  All original brands and custom responses remain in the preference panel,
  including brands that Qloo has not resolved.
- Evidence buttons focus the inspiration gallery and show supporting images;
  “Show all inspirations” restores the gallery. Expand a look for its observed
  garments, palette, silhouettes, styling, possible materials, and uncertainties.
- Evidence/observations attach to an image only if its ID and saved version
  timestamp match the analysis source. A replacement image does not inherit
  observations from the previous file.
- Missing analysis shows “Discover my style”; explicit activation POSTs to the
  existing analysis endpoint. “Regenerate analysis” uses `?force=true` and can
  incur a new model request. Loading the dashboard or inspecting evidence does not.
- Running analyses resume status checks after refresh. Polling is bounded;
  abandoned runs become retryable after the existing backend's 15-minute lease.
- Outdated analyses are labelled. Provider failures preserve the previous
  successful analysis where available, with a clear retry state.
- Partial onboarding shows a continuation action instead of triggering analysis.
- “Edit preferences” opens `/taste-test?edit=1`. “Manage inspirations” opens
  `/taste-test?edit=1&step=inspirations`, reusing the existing upload, replacement,
  removal, validation, and background save flow. Finishing returns to the dashboard.
- Returning completed users opening `/taste-test` continue to `/dashboard`;
  explicit edit links preserve their saved choices and the “Jump to end” shortcut.

## Changes and setup

- `frontend/src/components/TasteDashboard.jsx`: dashboard, evidence links,
  palette, saved preferences, gallery, and analysis state management.
- `frontend/src/lib/tasteProfile.js`: question-label mapping, case/whitespace
  deduplication, image-version matching, and expired-run detection. This does
  not impose a canonical fashion taxonomy on the model's interpretations.
- `frontend/src/styles/dashboard.css` and `tokens.css`: responsive editorial
  layout and approximate color swatches.
- `App.jsx` and `TasteTest.jsx`: protected dashboard routing and edit/return links.
- `backend/app/analysis.py`: GET includes `previous_successful` for a failed or
  running latest run, always scoped to the authenticated owner. Existing
  successful-response fields and POST behavior remain compatible.
- Frontend and backend tests cover dashboard states, evidence, persistence,
  authentication gates, and prior-result isolation.

No new package, environment variable, or database migration is required for this
dashboard. Existing analysis migration `0003_taste_analysis` and backend Gemini
and Supabase credentials must already be configured. See [analysis setup](ANALYSIS.md).
Run the frontend with `npm run dev` and backend with the existing Uvicorn command.

## Qloo enrichment

The discovery page `/explore` includes **Brands to explore**, with explicit enrich/refresh,
Qloo provenance, validated fashion-brand categories, verified website links,
loading/empty/stale/failure states, and persistent hide/restore preferences.
Loading it reads saved enrichment only. Failures preserve prior results and
do not block the saved preferences, Gemini insights, or inspiration gallery.
See [setup, API behavior, and live verification](QLOO_ENRICHMENT.md).

The discovery page **Find products** panel connects four verified Qloo brand stores and offers
external searches for SHEIN, Myntra, AJIO, Amazon Fashion, Flipkart, and Nykaa
Fashion. It reads source capabilities on load and searches only on submission.
Filters, current taste ranking, real variant links, and partial/empty/error
states are implemented. Shopping habits remain separate from favorite-brand
signals. See [product-search behavior and setup](PRODUCT_SEARCH.md).
Direct editing of individual Gemini-inferred attributes remains future work;
Qloo affinities can already be dismissed and restored.

## Verification

Verified 42 frontend tests, 47 backend tests, and the Vite production build.
Browser checks in isolated Edge cover 375, 768, 1024, and 1440px, saved brands,
private-preview rendering, keyboard evidence navigation, regeneration, empty,
failed, incomplete, stale, and signed-out states. Screenshots were visually
reviewed; status notices appear above the overview and mobile headings stay
compact. No horizontal overflow or page runtime errors were found.

Browser authentication/API responses are mocked. The fixture uses the actual
saved Gemini analysis with illustrative local images, so these checks do not
claim a new live login or image-analysis run. The ignored screenshots/script
are under `test-results/dashboard/`. Unit tests verify image-version matching,
URL cleanup, and running-analysis refresh behavior; backend tests verify that
prior results remain accessible only to their owner.

## Discovery page relocation

Product search and Qloo enrichment are mounted only on `/explore`. Dashboard
navigation and its final discovery link open that page. The home-page search
section sits before **How it works** and submits `q` through a GET form. Discovery
pre-fills that query and waits for an explicit product search. Signed-out users
see sign-in on the same URL; OAuth callbacks resume the stored discovery URL
in the same tab. Only `/explore` destinations are accepted for this return.
The Python frontend route list also includes `/explore` for direct navigation.

Relocation checks: 65 frontend tests passed, plus five focused return-navigation
tests; five backend API tests passed including the discovery frontend route.
The final production build and whitespace checks passed.

## Extension product direction

Product search has moved to the downloadable browser extension. `/explore` now
shows Qloo brand affinities and privately saved extension product bookmarks.
The home discovery section links to brand exploration and downloads the ZIP;
`/extension` explains loading unpacked, and `/extension/connect` pairs the account
only after explicit approval. See [extension documentation](EXTENSION.md).


## Visual taste analytics

The dashboard includes a compact overview and four data-driven visualizations:

- Inspiration mix: switch between aesthetics, fits, patterns, and garments. Each
  bar counts distinct unchanged images with that saved Gemini observation.
  Clicking a bar or supporting thumbnail opens its evidence in the gallery.
- Color balance: a donut chart of color observations, deduplicated per image.
  Multiple colors per image are allowed, so observations are not percentages of
  the image collection or measured pixel proportions. Swatches are approximate.
- Qloo cultural connections: counts of distinct resolved entities/tags by input
  group, selectable source-interest chips, and the first saved brand ranks.
  Counts are not contribution weights or confidence scores. Hidden brands are
  excluded and earlier runs are marked stale.
- Shopping corrections: latest saved correction per product, grouped by reason.
  Counts are not click history, purchases, or conversion rates. Saved bookmarks
  are counted separately. With no feedback, a getting-started prompt replaces
  the empty chart.

`GET /api/onboarding/analytics` returns authenticated owner-scoped Qloo and
shopping summaries without invoking providers or changing profile data. All
figures are derived from existing records; no additional migration is needed
beyond the existing feedback migration. Loading failures leave inspiration
charts available, show unavailable counts as dashes, and offer a retry.

The written style story and detailed interpretation are expandable, while the
analytics and private image gallery remain directly accessible. No new chart
library is required. The responsive layout has keyboard-accessible controls,
chart labels, source captions, and evidence links.
