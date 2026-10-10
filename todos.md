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
support saved aesthetics. Live Supabase configuration and browser checks
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
verify real email/Google flows. Dashboard, collections, account settings,
and uploaded-image deletion remain pending.

**Done when:** A user can return later and find their own saved data.

## Phase 3 --- Taste test and inspiration upload

**Outcome:** Muselly learns initial preferences from choices and images.

-   [ ] Build a multi-step visual taste test with outfit/style choices.
-   [ ] Collect preferred colors, fits, aesthetics, occasions, and
    dislikes.
-   [ ] Allow users to upload multiple outfit images and screenshots.
-   [ ] Show image previews, remove/retry, upload progress, and error
    states.
-   [ ] Save taste-test answers and inspiration images to the account.
-   [ ] Allow skipping optional questions and editing answers later.

**Done when:** A new user can finish onboarding using the test, uploads,
or both.

## Phase 4 --- AI taste analysis and Qloo enrichment

**Outcome:** Inputs become an understandable, editable Style DNA.

-   [ ] Use a vision model to extract colors, silhouettes, garment
    types, and aesthetic descriptors from uploaded images.
-   [ ] Normalize overlapping attributes and combine them with
    taste-test answers.
-   [ ] Match supported brands/cultural interests to valid Qloo entities
    or tags.
-   [ ] Query Qloo for relevant affinities; keep unsupported attributes
    in your own style model.
-   [ ] Store the resulting profile with source information (test,
    image, or Qloo).
-   [ ] Build a **Style DNA** view: top aesthetics, palette, fits,
    inspiration gallery, and optional affinities.
-   [ ] Let users correct or remove inferred preferences and regenerate
    the profile.
-   [ ] Handle Qloo/API failures gracefully without blocking basic
    visual profiling.

**Done when:** A user sees a plausible profile, can explain where its
signals came from, and can edit it.

## Phase 5 --- Dashboard and inspiration library

**Outcome:** The dashboard becomes the home for personal style.

-   [ ] Build dashboard overview with **Shop my taste**, Style DNA
    summary, and recent inspirations.
-   [ ] Add an inspiration library with image cards and delete/save
    actions.
-   [ ] Add simple collections or tags (e.g., Farewell, Casual,
    Workwear).
-   [ ] Provide **Add inspiration** from the dashboard.
-   [ ] Show recent searches and saved product recommendations.
-   [ ] Keep dashboard layout consistent with `style.md`.

**Done when:** A user can manage inspirations and start shopping from
one place.

## Phase 6 --- AI shopping search

**Outcome:** Users can ask for outfits in natural language.

-   [ ] Add a search box for prompts such as "Find a farewell dress
    under ₹3,000."
-   [ ] Parse category, occasion, budget, color, fit, and other
    constraints.
-   [ ] Show editable filters before or after searching.
-   [ ] Add retailer selection: Amazon, Flipkart, Meesho, Myntra, AJIO,
    Urbanic, Savana.
-   [ ] Connect at least **one legitimate, permitted source of product
    listings** with title, image, price, URL, and retailer.
-   [ ] Add a second retailer/source only after the first is reliable.
-   [ ] Implement loading, empty, failed-search, and
    unsupported-retailer states.
-   [ ] Do not show invented live prices, stock, or listings.

**Done when:** A user submits a query and receives real linked products
from at least one supported source.

## Phase 7 --- Taste ranking and recommendation cards

**Outcome:** Search results are personalized rather than generic.

-   [ ] Rank retrieved products using query fit, visual attributes, user
    preferences, and applicable Qloo-enriched signals.
-   [ ] Apply hard constraints (especially budget and selected retailer)
    before ranking.
-   [ ] Display product image, name, price, retailer, and **View on
    retailer** link.
-   [ ] Add **Why this matches** with specific, grounded explanations.
-   [ ] Show match percentages only if a documented ranking calculation
    exists; otherwise use descriptive labels.
-   [ ] Add **Save product** and **Not my style** feedback.
-   [ ] Provide a simple **Generic vs My Taste** comparison for the
    hackathon demo.

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
-   [ ] Add upload limits, image validation, consent messaging, and
    deletion controls.
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

**Configure Supabase and verify Phase 2 sign-in and saved taste selections.**
Then continue the remaining Phase 3 test and upload features; do not build all retailer integrations or advanced
agent workflows before a single end-to-end shopping path works.
