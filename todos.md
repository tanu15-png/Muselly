# Muselly --- Feature Development TODOs

> **Goal:** Build a working, demo-ready AI taste-shopping experience:
> discover personal style, search for outfits, get explainable retailer
> recommendations, and use that style while browsing.
>
> **How to use:** Complete phases in order. Tick a feature only when the
> user can actually use it end-to-end. Read `README.md` for product
> behavior and `style.md` for UI consistency.

## Technology stack

**React + Vite frontend · Python + FastAPI backend · Supabase Auth and
PostgreSQL · SQLAlchemy models · Alembic migrations.** Node.js/npm are
frontend build tools. See [setup instructions](docs/SETUP.md).

## Phase 1 --- Landing page and entry flow

**Outcome:** A visitor understands Muselly and can start onboarding.

-   [x] Build the responsive landing page using the approved Muselly
    design.
-   [x] Add navigation anchors: **How it works · For you · Extension ·
    FAQs**.
-   [x] Add **Sign in** and **Get started** actions; show **Start taste test** only after verified sign-in.
-   [x] Build the How it works, For you, Extension and FAQs sections.
-   [x] Add **Get Extension** CTA (show "Coming soon" until the
    extension is published).
-   [ ] Ensure the landing page works on mobile.
    Responsive layouts and accessible mobile navigation are implemented;
    final browser checks at 375, 768, 1024, and 1440px remain pending because
    this implementation environment blocks local listening sockets.

**Done when:** A new visitor can navigate the page and reach the taste
test.

**Current implementation:** React landing page and taste-test entry are
available. Email/password and Google sign-in use Supabase, with server
verification in the Python API. SQLAlchemy models and Alembic migrations
support saved aesthetics, questionnaire drafts, and image metadata. Live auth checks
remain necessary before marking authentication as verified end-to-end.

## Phase 2 --- Authentication and user account

**Outcome:** Each user has a private, persistent Muselly account.

-   [ ] Implement sign-up, sign-in, sign-out, and session persistence.
-   [ ] Protect the dashboard, taste profile, and saved collections.
-   [ ] Create a user profile record in the database.
-   [ ] Show onboarding for first-time users and dashboard for returning
    users.
-   [ ] Add basic account settings and a way to delete uploaded
    inspirations.

**Implementation available:** Supabase email sign-up/sign-in, Google OAuth,
sign-out, session refresh, protected taste-test APIs, and user/taste models
are implemented. Configure the Supabase project, apply migrations, and
verify real email/Google flows. The taste dashboard is implemented; collections
and account settings remain pending. Onboarding image deletion is implemented
in Phase 3.

**Done when:** A user can return later and find their own saved data.

## Phase 3 --- Taste test and inspiration upload

**Outcome:** Muselly collects initial preferences and private inspirations.

-   [x] Build a multi-step visual taste test with outfit/style choices.
-   [x] Collect preferred colors, fits, aesthetics, occasions, and
    dislikes.
-   [x] Allow users to upload multiple outfit images and screenshots.
    Five user-uploaded private images were retrieved successfully for the live
    analysis run on 2026-10-10; upload validation/retry tests also pass.
-   [x] Show image previews, remove/retry, upload progress, and error
    states.
-   [x] Save taste-test answers and inspiration images to the account.
    Verified a completed live account with 19 saved answers (one optional
    question omitted), five image records, and five readable private objects.
-   [x] Allow skipping optional questions and editing answers later.

**Done when:** A new user completes all required answers and uploads 5–10
inspiration images successfully, then returns to their taste dashboard.

**Implemented:** Twenty questions across five stages, including optional Q20
current city/region and country. Reusable image choices, swatches, chips, tags,
Other fields, maximum selections, exclusive dislikes, a coalescing background
save queue, immediate Back/Continue/Skip, and saved completed-state editing. Images support multi-file
browse/drop, byte progress, private authenticated previews, retry, removal,
and atomic replacement. Backend validation checks image contents, size, pixels,
and required answers. Completion confirms 5–10 durable storage objects.
The dashboard route now displays saved preferences, private inspirations, and
actual Gemini analysis, with explicit generation/regeneration actions (Phase 4).
Qloo enrichment is implemented with backend-only API access, versioned runs,
normalized provenance, dashboard controls, and persistent affinity dismissal.
Live Qloo verification requires configuring the account key. Shopping
recommendations remain future work. See [the enrichment guide](docs/QLOO_ENRICHMENT.md).

**Verification (2026-10-10):** React interaction tests include the complete
20-question flow. Backend tests cover temporary migrated databases, mocked
Supabase Auth/Storage, validation, completion, and user isolation. Production
build passes. Chromium checks cover 375, 768, 1024, and 1440px for question,
destination, aesthetic, silhouette, occasion, and upload layouts, plus keyboard
selection, five-image upload/completion, and signed-out redirects. Browser API
responses are mocked; this does not certify live uploads. Screenshots and
checks are in ignored `test-results/taste/`.

**Live setup:** `0002_taste_test` is applied to the configured Supabase project.
Read-only verification confirms the private bucket, 10 MB object limit, RLS on
both new tables, no browser storage policies, and no authenticated Data API
SELECT grants. An earlier anon/public credential correctly failed a private
upload, and isolated test records were removed. The backend credential is now
working: all five actual user uploads were read from private Storage during
analysis. Live replacement/deletion have not been exercised in this analysis
task; those operations remain covered by automated mocked-Storage tests.

See [implementation/setup notes](docs/TASTE_TEST.md).

## Phase 4 --- AI taste analysis and Qloo enrichment

**Outcome:** Inputs become an understandable, editable Style DNA.

-   [x] Use a vision model to extract colors, silhouettes, garment
    types, and aesthetic descriptors from uploaded images.
-   [x] Expose authenticated backend analysis endpoints and save versioned
    JSON runs with questionnaire/image sources, model, token usage, timestamps,
    cache reuse, stale detection, and sanitized failure/retry states.
-   [x] Normalize overlapping attributes and combine them with
    taste-test answers.
-   [x] Match supported brands/cultural interests to valid Qloo entities
    or tags.
-   [x] Query Qloo for relevant affinities; keep unsupported attributes
    in your own style model.
-   [x] Store the resulting profile with source information (test,
    image, or Qloo).
-   [x] Build a **Style DNA** view: top aesthetics, palette, fits,
    inspiration gallery, and optional affinities.
    The taste dashboard displays actual Gemini interpretations with image
    evidence and the original questionnaire. Qloo affinities have explicit generation/refresh, source labels, and hide/restore controls.
-   [ ] Let users correct or remove inferred preferences and regenerate
    the profile.
    Qloo affinities can be hidden/restored; direct Gemini-attribute editing remains pending.
-   [x] Handle Qloo/API failures gracefully without blocking basic
    visual profiling.

**Done when:** A user sees a plausible profile, can explain where its
signals came from, and can edit it.

**Backend verification (2026-10-10):** Migration `0003_taste_analysis` is
applied. An actual Gemini run analyzed the saved 19 answers and five private
images, and persisted a schema-validated result. `gemini-3.8-flash` and
`gemini-3.5-flash` were overloaded, so the successful run used
`gemini-3-flash-preview`; `backend/.env` now selects that model. GET/POST
`/api/onboarding/analysis` are available in the running API; unauthenticated
GET returns 401. The full provider schema was rejected, so a live-verified
simplified wire schema is used while full backend validation remains strict.
Analysis JSON includes per-image observations, recurring signals, questionnaire
interpretation, evidence-linked conflicts, and limitations. At that checkpoint,
normalization and Qloo remained pending; they are now implemented as documented
in [the enrichment guide](docs/QLOO_ENRICHMENT.md). Direct inferred-attribute
editing and shopping recommendations remain pending. All 46 backend tests pass, including migration consistency, owner
isolation, cached/forced runs, stale snapshots, timeouts, overload responses,
invalid model output/evidence, and retry behavior. See
[analysis API documentation](docs/ANALYSIS.md).

## Phase 5 --- Dashboard and inspiration library

**Outcome:** The dashboard becomes the home for personal style.

-   [x] Build dashboard overview with Style DNA summary and recent inspirations.
-   [x] Add **Shop my taste** search once a real product source is integrated.
-   [x] Display saved questionnaire preferences, evidence-linked AI insights,
    and private inspiration cards on the authenticated dashboard.
-   [ ] Add an inspiration library with image cards and delete/save
    actions.
    The gallery and “Manage inspirations” link are implemented; direct card
    save/delete actions and collections remain future work.
-   [ ] Add simple collections or tags (e.g., Farewell, Casual,
    Workwear).
-   [x] Provide **Add inspiration** from the dashboard.
    “Manage inspirations” opens the existing validated upload stage directly.
-   [ ] Show recent searches and saved product recommendations.
-   [x] Keep dashboard layout consistent with `style.md`.

**Dashboard verification (2026-10-16):** Responsive editorial layout, private
previews, original brand/custom answers, keyboard evidence navigation, explicit
regeneration, stale-version detection, previous-result preservation, failed/empty/
incomplete states, and signed-out redirects are verified. All 42 frontend tests
and 47 backend tests pass; production build passes. Edge checks cover 375, 768,
1024, and 1440px with no horizontal overflow or runtime errors. Browser Auth/API
responses are mocked, using the actual saved analysis fixture and illustrative
local images; this is not a new live Supabase login or Gemini run. Screenshots
and the check script are ignored under `test-results/dashboard/`.

That dashboard checkpoint preceded Qloo integration. The current enrichment
panel needs backend Qloo configuration and migration `0004_qloo_enrichment`,
with no added package dependencies.
See [dashboard implementation notes](docs/DASHBOARD.md).

**Done when:** A user can manage inspirations and start shopping from
one place.

## Phase 6 --- AI shopping search

**Outcome:** Users can ask for outfits in natural language.

-   [x] Add a search box for prompts such as "Find a farewell dress
    under ₹3,000."
-   [x] Parse category, occasion, budget, color, fit, and other
    constraints.
-   [x] Show editable filters before or after searching.
-   [x] Add source selection: four connected Qloo brand stores and external
    search links for SHEIN, Myntra, AJIO, Amazon Fashion, Flipkart, Nykaa Fashion.
-   [x] Connect at least **one legitimate, permitted source of product
    listings** with title, image, price, URL, and retailer.
-   [x] Add a second retailer/source only after the first is reliable.
-   [x] Implement loading, empty, failed-search, and
    unsupported-retailer states.
-   [x] Do not show invented live prices, stock, or listings.

**Done when:** A user submits a query and receives real linked products
from at least one supported source.

## Phase 7 --- Taste ranking and recommendation cards

**Outcome:** Search results are personalized rather than generic.

-   [x] Rank retrieved products using query fit, visual attributes, user
    preferences, and applicable Qloo-enriched signals.
-   [x] Apply hard constraints (especially budget and selected retailer)
    before ranking.
-   [x] Display product image, name, price, retailer, and **View on
    retailer** link.
-   [x] Add **Why this matches** with specific, grounded explanations.
-   [x] Show match percentages only if a documented ranking calculation
    exists; otherwise use descriptive labels.
-   [ ] Add **Save product** and **Not my style** feedback.
-   [x] Provide a simple **Generic vs My Taste** comparison for the
    hackathon demo.

Implemented ranking modes: **My taste** and **Search relevance**. Common English
query parsing is deterministic; product search makes no additional AI request.
See [implementation and limitations](docs/PRODUCT_SEARCH.md).

**Done when:** Two different taste profiles can receive meaningfully
different rankings for the same query.

## Phase 8 --- Chrome extension: capture and analyze

**Outcome:** Muselly follows users while they browse.

-   [ ] Create a Manifest V3 extension with the same Muselly visual
    identity.
-   [ ] Add extension sign-in/session connection to the Muselly account.
-   [ ] Add **Save image to Muselly** on supported pages, including
    Pinterest images where permitted.
-   [ ] Add **Analyze this product** on a supported retailer product
    page.
-   [ ] Add **Find similar** using the current product as inspiration.
-   [ ] Sync saved images and products back to the website dashboard.
-   [ ] Show clear permissions, unsupported-site messages, and error
    states.

**Done when:** Saving an inspiration from a browser page makes it appear
in the dashboard.

## Phase 9 --- Chrome extension: taste filter

**Outcome:** Users can personalize a retailer's existing results page.

-   [ ] Support **one retailer search-results page** first.
-   [ ] Read permitted visible product cards (title, image, price,
    link).
-   [ ] Add **Filter by my taste** in the extension popup or sidebar.
-   [ ] Highlight high matches and optionally dim low matches without
    breaking retailer controls.
-   [ ] Add an on-page **Save** action for a selected item.
-   [ ] Offer **Find better matches** in the extension side panel.
-   [ ] Test pagination, lazy loading, layout changes, and extension-off
    behavior.
-   [ ] Add more retailers only after the first works reliably.

**Done when:** The user can toggle taste filtering on a supported
retailer page and see a clear difference.

## Phase 10 --- Quality, privacy, and demo readiness

**Outcome:** The complete experience is reliable enough to show judges.

-   [ ] Test full journey: landing → sign in → taste test/upload → Style
    DNA → search → recommendations → retailer redirect.
-   [ ] Test extension journey: browse → save inspiration → dashboard
    sync → taste-filter products.
-   [ ] Verify that private images and taste profiles are accessible
    only to their owner.
-   [ ] Secure API keys on the backend; never ship Qloo or LLM secrets
    in frontend/extension code.
-   [x] Add upload limits, image validation, consent messaging, and
    deletion controls.
    Verified through frontend/backend tests; live Storage acceptance remains
    tracked under Phase 3.
-   [ ] Test responsive layouts, keyboard accessibility, broken links,
    and slow API responses.
-   [ ] Deploy website/backend and package the extension for demo.
-   [ ] Prepare a short demo with two distinct taste profiles and the
    same shopping query.
-   [ ] Document what Qloo contributes versus the vision model and
    product search.
-   [ ] Update README with working setup, demo link, screenshots, and
    known limitations.

**Done when:** A judge can see the complete workflow without relying on
fake API results.

------------------------------------------------------------------------

## MVP cut line

**Must ship for the hackathon** - Landing page and sign-in - Taste
test + image upload - Style DNA with meaningful Qloo integration -
Dashboard + saved inspirations - Natural-language search + retailer
filters - Real product source + personalized ranking + retailer links -
Basic extension: save image and filter one supported retailer -
End-to-end deployed demo

**Stretch goals (only if core MVP is working)** - \[ \] Full Pinterest
account/board connection (subject to API permissions) - \[ \] Additional
retailer integrations - \[ \] Outfit bundles within a total budget - \[
\] Multi-user/group taste recommendations - \[ \] Taste
evolution/history analytics - \[ \] Price alerts, checkout, or order
tracking

## Next action

**Configure Qloo credentials and verify live coverage using [the capability check](docs/QLOO_ENRICHMENT.md), then implement the first retailer product adapter.**
The questionnaire, private inspirations, Gemini analysis, and dashboard are
implemented, including Qloo enrichment. Unsupported brands retain their original
preferences. Configure the backend Qloo key and run the capability check before
claiming live coverage; product retrieval and recommendations remain future work.

## Implemented extension direction — 2026-10-19

- [x] Website restricted to taste/Style DNA, Qloo brands, inspirations, and saved finds.
- [x] Get Extension downloads a credential-free Manifest V3 ZIP with installation guide.
- [x] Explicit nonce-based account pairing with verified owner context.
- [x] Prompt-based retailer searches and ranking of up to 100 loaded cards.
- [x] Visible-tab snapshots, crop preview, image upload, and Find similar.
- [x] Private product bookmarks and private inspiration snapshot uploads.
- [x] Persistent extension prompts/results and account-isolated workspace.
- [x] Saved-products migration, owner isolation, extraction and messaging tests.
- [ ] Publish a store listing for one-click installation.
- [ ] Expand live retailer coverage and monitor layout changes.

See [current behavior and verification](docs/EXTENSION.md).
