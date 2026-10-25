# Product search

> Website product search is superseded by the [browser extension](EXTENSION.md).
> The old components/endpoints remain for compatibility; the current website
> mounts Qloo exploration and saved finds only. The extension ranks loaded
> retailer products. The catalog implementation below records the earlier phase.


The dedicated `/explore` page searches real products from four accessible
brand stores discovered through Qloo. There is no new model call, API key,
package, or database migration for shopping search. Existing authentication,
saved preferences, analysis, and enrichment remain prerequisites for their
respective personalization signals; search also works without enrichment.

## Coverage

| Source | Current behavior |
| --- | --- |
| AVIA | Live product cards through public Shopify Storefront API |
| Prabal Gurung | Live product cards through public Shopify Storefront API |
| Sachin & Babi | Live product cards through public Shopify Storefront API |
| Marchesa | Live product cards through public Shopify Storefront API |
| SHEIN, Myntra, AJIO, Amazon Fashion, Flipkart, Nykaa Fashion | External search links; no product feed or product cards |

Source hosts, Qloo entity IDs, and retailer URL templates are maintained in
`shared/shopping-sources.json`. A Qloo recommendation alone does not establish
catalog access. Further brands need a verified, supported product source before
they can supply cards. Qloo affinity badges and ranking boosts appear only when
that brand is in the user's current, non-dismissed enrichment.

The backend uses Shopify's versioned, tokenless **Storefront GraphQL API**
(`2026-10`), querying public product/search fields. It does not scrape storefront
HTML or use the theme-only Ajax API. Product URLs point to the real store and
selected available variant; images and prices come from the store response.
Availability is checked at retrieval time and can change before checkout.

## User flow and constraints

After starting the existing backend and frontend, use the home-page search
section before **How it works**, or open `/explore` directly. Sign in to use
product search and Qloo brand discovery. The home query carries into the new
page and survives email sign-in or an OAuth return in the same tab. Try **A midi dress for an evening party**. Select
stores and submit explicitly; opening discovery only loads saved enrichment and source metadata. The Style
DNA dashboard links to discovery and does not mount either search panel.
The four stores cover sportswear and designer fashion, so an inexpensive dress
query can correctly return no matches.

Common English product categories, colors, fits, occasions, size phrases, and
budgets such as `under ₹3,000`, `under $50`, or `between 3k and 5k` are parsed
deterministically. This is a bounded vocabulary, not general language reasoning.
Editable controls override inferred values. Occasion guides ranking; category,
recognized garment details, fit, color, size, and budget constrain matches.
Sizes use each store's labels without size-system conversion. A single available
variant must satisfy size, color, and budget together. Explicit saved dislikes
are also enforced when supported by product metadata.

Each source returns at most 12 candidate products and 32 variants per product.
Searches are not exhaustive, and pagination is not implemented. A missing match
does not mean a store has no suitable inventory. Partial failures retain results
from working stores; total catalog failure offers a retry. External retailer
links carry shopping keywords, while further filtering takes place on that site.

## Ranking and prices

Candidate relevance counts matching query words in product metadata and adds
two points for matching occasion terms. **My taste** additionally adds:

| Evidence | Boost |
| --- | --- |
| Saved aesthetic supported by product text | 2 |
| Saved color preference supported by selected variant/title | 3 |
| Saved fit supported by product text | 3 |
| Current inspiration-analysis attribute supported by product text | 2 |
| Current, non-dismissed Qloo affinity for this store | 1 |

Each signal contributes once. **Search relevance** removes those personal
boosts while retaining explicit filters and dislikes. Price sorting uses the
same filtered candidates. Explanations cite the evidence that contributed;
there is no match percentage or visual similarity claim. Gemini observations
and Qloo affinities are excluded if their saved source fingerprint is outdated.
Stated preferences remain authoritative. Profile context is read for the
authenticated owner only and is not sent to the product providers.

Display/budget currencies are INR and USD. Cross-currency calculations use the
ECB daily reference feed and Decimal arithmetic; the response includes the
rate date. Converted prices are labelled estimates alongside original prices.
Budget comparisons occur before display rounding. Taxes, duties, shipping,
payment-provider exchange rates, and delivery eligibility are not calculated.
If current rates cannot be fetched, the request fails with a recoverable error
rather than inventing a conversion. Rates older than seven days are rejected.

## API and operation

Both routes require the existing Supabase bearer authentication:

- `GET /api/search/sources`: source IDs, names, websites, modes, current Qloo
  badges, and default selection; no store/model request.
- `POST /api/search/products`: query, selected `source_ids`, optional `category`,
  `color`, `size`, `fit`, `occasion`, `min_price`, `max_price`, `currency`, and
  `sort` (`personalized`, `relevance`, `price_asc`, `price_desc`).

Example request body:

```json
{
  "query": "A midi dress for an evening party",
  "source_ids": ["prabal-gurung", "sachin-babi", "marchesa"],
  "currency": "INR",
  "sort": "personalized"
}
```

Responses include `products`, `applied_filters`, `source_statuses`,
`retailer_links`, `exchange`, and retrieval timestamps. Selecting only external
retailers returns `external_only` and search links. Unknown sources and invalid
budgets return 422; repeated searches are limited to ten per owner per minute.
Source failures are sanitized; provider details and keys are not returned.

Four worker threads query fixed store hosts with 10-second HTTP timeouts and a
15-second aggregate wait. Public catalog queries are cached for five minutes,
bounded to 128 entries; ECB rates are cached for six hours. Personalized results
are computed separately for every owner. These caches and rate limits are local
to each backend process. No search history or product saves are persisted.

Implementation: `backend/app/catalog.py`, `backend/app/shopping.py`, and
`frontend/src/components/ProductSearch.jsx`, and `ExplorePage.jsx`. No environment changes are needed;
outbound HTTPS to the fixed Shopify stores and ECB feed must be available.

## Verification

Backend search tests cover authentication, owner isolation, fixed source
validation, real variant normalization, safe links/images, currency conversion,
same-variant constraints, dislikes, current analysis/Qloo signals, personalization
versus relevance, provider failures, external-only searches, and rate limits.
Frontend tests cover explicit submission, filters/source selection, product
cards, explanations, external links, broken images, partial results, and failure
recovery. Run from their respective directories:

```bash
# backend/
.venv/bin/python -m pytest tests/test_shopping.py -q
# frontend/
npm test
npm run build
```

Live checks on 2026-10-18 verified tokenless access to all four stores. A query
for midi dresses across the three designer stores returned 30 filtered products
from 36 candidates, with actual available variant links and ECB rates dated
2026-10-16. This verifies provider retrieval/filtering, not a purchase or a new
Supabase sign-in. These stores' designer prices are retained as returned.

The full backend suite passed 93 tests; the final search-specific rerun passed
20 tests. The full frontend suite passed 62 tests, and the production build
passed. The dashboard and search are loaded in separate bundles.

Primary API references: [Shopify tokenless Storefront access](https://shopify.dev/docs/api/storefront/2026-10),
[product search](https://shopify.dev/docs/api/storefront/2026-10/queries/search),
[product variants](https://shopify.dev/docs/api/storefront/2026-10/objects/ProductVariant),
and [ECB reference rates](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html).

Next work: product saving/feedback and search history; broader source coverage
through approved retailer APIs/affiliate feeds; pagination and improved parsing.

## Returning to discovery

Internal navigation uses browser history without reloading the document. The
authentication provider retains verified content when Supabase emits the same
access token again, as can happen when switching tabs. A changed token is still
verified with the backend.

Discovery keeps a per-account cache in the current tab's session storage. Saved
brand affinities and source metadata are fresh for five minutes. Older entries
remain visible while a background GET checks for updates; entries expire after
thirty minutes. Running enrichment continues status checks. Explicit enrichment,
refresh, hide, and restore still call the backend and update the cache. No Qloo
generation is triggered by reopening the page.

The last search query, filters, selected stores, and full response (including
zero-product responses) are saved separately in per-account local storage, with
a session-storage fallback. This snapshot has no automatic expiry and survives
reloads and browser sessions while the user remains signed in. Its original
search time is displayed with a prompt to search again for current prices,
availability, and taste matches. Profile edits invalidate the short-lived
context cache but retain the clearly labelled previous search. Explicit sign-out
clears both kinds of storage. A new explicit home query does not show the old
query's results or discard the completed search before a replacement succeeds.
Successful searches also synchronize the URL query, so returning through browser
history restores an edited search correctly. Storage failures leave normal
searching available. No access tokens are saved in these caches, and they never
establish authentication.

Caching/navigation verification: all 79 frontend tests and the production build
pass. Tests cover returning without another saved-affinity request, background
revalidation, per-account isolation, expiry, storage failure, explicit refresh,
restored products, same-token auth events, sign-out cleanup, and internal history
navigation.

Persistent-search verification: 84 frontend tests pass, including returning after
a day with session storage cleared, preserving zero-result responses, retaining
snapshots through profile-cache invalidation, account isolation, edited query
URLs, and retaining the prior completed search while exploring a new query.
