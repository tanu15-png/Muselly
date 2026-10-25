# Qloo enrichment execution plan

Status: implemented in `backend/app/qloo.py` and `backend/app/enrichment.py`.
The design plan below is retained as historical context. For the current
Qloo-led extension flow, product corrections, and liked-brand signals, see
[the extension guide](EXTENSION.md). Migration `0006_product_feedback` adds
private correction storage. Product likes join explicit interests on the next
user-triggered Qloo refresh; snapshots only save private inspirations.

## Shopping destinations

Use SHEIN, Myntra, AJIO, Amazon Fashion, Flipkart, and Nykaa Fashion for the
planned explore/search filters. These are shopping destinations, while favorite
fashion brands such as Zara and Nike are taste signals. A selected marketplace
must not imply that the user likes every brand sold there. Qloo coverage and
product-data access must be verified independently for each destination.

Landing-page names, FAQs, the shopping-habits question, and the roadmap now use
this list. The questionnaire retains old option IDs for Meesho, Urbanic, and
Savana, hidden unless already selected. Existing saved answers and dashboard
labels therefore keep their meaning. Favorite-brand answers remain independent.

## 1. Verify API access and useful coverage

Configure backend-only `QLOO_API_KEY` and `QLOO_BASE_URL` during implementation.
The current public documentation uses `https://api.qloo.com`; use the hackathon
host only if provisioned for the actual key. Never put the key in a VITE variable.
Authenticate server-side with `X-Api-Key`.

First run a bounded capability check: resolve known favorite brands and a few
explicitly named music/cultural interests, then request related brands. Record
which of the six shopping destinations resolve, which are ambiguous, which
lack coverage, and which endpoints/parameters the account supports. Do not
assume an entity exists because an LLM recognizes the name. This check is the
first acceptance gate before building the dashboard integration.

## 2. Normalize the existing profile

Create a versioned profile representation that keeps three sources separate:
user-stated preferences, Gemini image observations, and Qloo affinities.
Store original labels alongside normalized values, question/image references,
and uncertainty. Explicit dislikes, budgets, sizes, occasions, and selected
retailers remain authoritative constraints; inferred signals cannot override them.

Inputs to resolution: favorite brands (q13), explicitly named artists (q7), and
named inspirations (q8) where a supported entity type fits. Broad cultural
interests (q14) can map only to tags actually discovered in Qloo. Shopping
habits (q16) remain destination preferences, with any marketplace affinity
kept distinct from fashion-brand preference. Colors, cuts, fabrics, generic
aesthetics, and unresolvable names remain useful local profile attributes.
Do not send raw photos, email, account ID, exact location, or the full free-text
questionnaire to Qloo. Demographic enrichment is outside this first increment.

## 3. Resolve entities and tags

Implement `backend/app/qloo.py` using the existing httpx dependency. Query
`GET /search` with `query` and the documented Search `types` values. Use
`GET /v2/tags` for supported tag IDs. Search types and Insights URNs must be
validated independently against the current API contract.

For each mapping save original input, source question, candidate Qloo ID/name,
entity subtype, resolution method, timestamp, and resolved/ambiguous/unsupported
status. Validate name or alias, entity category, and identifying metadata.
Never substitute a similarly named restaurant or place for a fashion brand.
Ambiguous candidates require confirmation or remain unresolved. Cache verified
mappings and short-lived no-results responses, with account/host-aware keys.

## 4. Request and validate affinities

Call `GET /v2/insights` with `filter.type=urn:entity:brand`, validated IDs in
`signal.interests.entities`, and supported tag signals only where relevant.
Apply fashion-category filters only after discovering valid tags. Preserve
provider IDs, labels, rank/score fields if returned, input signals, timestamps,
and provenance. Do not present Qloo scores as purchase probabilities or outfit
match percentages. Keep broad cultural affinities separate from fashion results.

Skip enrichment when there are no valid signals. Empty results mean no usable
affinity, not permission to invent one. Use bounded timeouts, rate limits,
limited retries for transient failures, and a capped result count. Avoid
retrying invalid credentials or malformed requests automatically.

## 5. Persist owner-scoped runs and expose endpoints

Add a new Alembic revision and an owner-scoped enrichment-run model, separate
from Gemini runs. Store source profile version/hash, analysis ID where relevant,
resolver version, resolved/unresolved mappings, validated result, status,
sanitized error, and creation/completion timestamps. Apply the same RLS and
browser-role restrictions as the existing private application tables.

Proposed API: authenticated `GET /api/onboarding/enrichment` reads the saved
run; `POST /api/onboarding/enrichment` explicitly generates it; `?force=true`
refreshes it. Read endpoints and page loads must not make provider calls.
Reuse matching inputs, mark changed inputs stale, serialize duplicate runs,
recover abandoned runs, and retain the prior successful result after failure.
Support removal/rejection of inferred affinities so later refreshes do not
silently restore preferences the user has rejected.

## 6. Add dashboard enrichment

Show related fashion brands and optional cultural affinities with a clear
Qloo source label, the user signals used, and unresolved-input notices.
Provide an explicit Enrich/Refresh action plus loading, empty, stale, failed,
and retry states. A Qloo failure must leave saved preferences, Gemini insights,
and the inspiration gallery usable. Explanations describe an affinity based
on supplied interests; they must not claim an image visibly contains a brand.

## 7. Connect explore/search after enrichment

Build a separate product adapter for each destination with verified data access.
Start with whichever of the six has a reliable permitted source. Each listing
needs retailer ID, product ID, title, product URL, image, brand, category,
price/currency, availability when available, and fetch timestamp. Add the other
adapters incrementally; never show invented stock or prices.

Search parses the user's request into editable constraints. Filter by retailer,
budget, category, availability and explicit dislikes first; rank remaining
products using visual/style fit, occasion fit, and a modest Qloo affinity signal
where actual product-brand mapping exists. Missing Qloo coverage must not
exclude an otherwise relevant product. Evaluate weights against contrasting
profiles and the same query before displaying a match estimate.

## Validation and completion gates

- Resolver tests: aliases, duplicate names, wrong entity types, ambiguous and
unsupported brands, invalid UUIDs, empty results, and provider schema drift.
- API tests: owner isolation, secret handling, caching, stale detection,
concurrent requests, 401/403, 429, timeouts, and previous-success retention.
- Profile tests: explicit constraints win; unsupported inputs survive; rejected
inferences stay rejected; changing analysis invalidates dependent enrichment.
- Dashboard tests: provenance, explicit trigger, retry, empty/stale/failure
states, and continued access when enrichment is unavailable.
- Live acceptance with the configured key: one correctly resolved input and
validated affinity response, or an explicit unsupported/empty outcome.
- Later search acceptance: real listings from at least one selected destination,
working product links, hard filters respected, explainable ranking, and no
invented data.

Implementation order: access/coverage check → normalized profile → resolver →
affinities → persistence/API → dashboard → first retailer adapter → ranking.
The first Qloo increment does not require six working retailer catalogs.

## References

Reviewed 2026-10-17 against Qloo's official public documentation:

- [API overview](https://github.com/qloo/docs-public/blob/main/reference/api-overview.md)
- [Entity Search parameters](https://github.com/qloo/docs-public/blob/main/reference/get-search.md)
- [Tag Search parameters](https://github.com/qloo/docs-public/blob/main/reference/get-tags.md)
- [Recommendation Insights](https://github.com/qloo/docs-public/blob/main/reference/basic-insights-use-case.md)
- [Parameters by entity type](https://github.com/qloo/docs-public/blob/main/reference/available-parameters-by-entity-type.md)

The references above describe the original design review, not a current live
coverage or recommendation-quality certification. Product feeds, retailer
availability, and subjective affinity quality require separate verification.
