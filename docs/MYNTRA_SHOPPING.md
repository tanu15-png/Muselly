# Shop your taste

`/shop` is the minimal authenticated shopping page. Its server-side catalog is the validated 1,500-product Myntra snapshot. The dashboard and landing-page navigation link to it; shopping sign-in returns here, including the OAuth callback.

## Customer flow

Describe clothing in English, for example “a floral midi dress for vacation under 3000” or “an everyday office outfit under 2000”. Category, explicitly named colors/details, negative details and numeric INR budgets are applied before ranking. Budget is per item: this page recommends pieces, not complete coordinated outfit bundles. The catalog contains women's clothing only. Requests for men/kids or unsupported products return an explicit empty state. Colors joined with “or” are alternatives. A country name alone does not establish weather or clothing suitability.

Results show actual catalog image URLs, listing prices, a brief ranking reason, Like/Not for me, and a direct Myntra link opening a new tab. My likes retrieves saved choices. Dislikes disappear immediately; Undo restores the previous preference. Prices, sizes and availability must be confirmed on Myntra, where checkout takes place. These are ordinary product links, not affiliate links.

## Ranking evidence

1. Explicit request constraints and saved questionnaire avoidance choices filter the catalog. A current explicit fit request can override a previous questionnaire fit avoidance.
2. Qloo's `/v2/insights` brand results use only verified cultural entity IDs from the customer's positive saved discoveries or still-current, previously resolved questionnaire interests. Familiar/disliked cultural entities are excluded. Only exact normalized brand names in the catalog receive a modest brand boost; no price or availability is inferred from Qloo. Requests use the existing bounded Qloo client and cache, and send no outfit prompt, private reference image, or location.
3. Explicit fashion connections supply clothing attributes from the reference images selected for that cultural entity. Only the owner's currently saved images with matching analysis timestamps count. Deleted/replaced references contribute nothing until valid analysis exists. Colors, patterns, silhouettes, garments and tentative material observations match product listing metadata. This is attribute matching, not pixel/embedding visual similarity; poster colors never establish garment preferences.
4. Likes boost the exact product and a bounded amount of similarity in listed details. Dislikes exclude the exact item, with only a small penalty for other items sharing multiple style details in the same category. A single dislike is not treated as a blanket rejection of a color or brand.

Reasons and API connection evidence identify the Qloo brand signal or the cultural entity plus supporting image IDs and matched attributes. Qloo outages retain local results and saved image-bridge ranking with an explicit degraded-state message. A customer without saved cultural inputs gets a link to build their direction rather than fabricated personalization.

## APIs and persistence

- `POST /api/shop/search`: authenticated request, owner-scoped taste evidence, bounded paging. Shares the existing search rate limit.
- `GET /api/shop/feedback`: authenticated current owner's choices for catalog products.
- `POST /api/shop/feedback`: catalog product ID plus `like`, `dislike` or `clear`. The server looks up all product data itself, reuses the existing `ProductFeedback` table, and serializes writes with the owner lock. No new migration is needed.

Browser feedback saves immediately in an owner-scoped local outbox and synchronizes in the background. Acknowledgements cannot delete a newer local change. Reload merges server preferences with pending local choices before replay. Search waits for pending choices to synchronize, ensuring the new ranking includes them. Offline failures remain on the device with retry controls. Account changes unmount/abort the old worker and requests verify the expected Supabase owner.

## Deployment

The JSON snapshot is deliberately Git-ignored. Copy `backend/data/myntra-1500/catalog-products.json` into the deployed backend, or set `MYNTRA_CATALOG_PATH` to an absolute file path. Missing/invalid data yields a clean 503, never mock products. The loader verifies women-only categories, prices, product IDs and allowed image/retailer URLs and caches by file modification metadata. It makes no Apify requests during shopping. Qloo's existing backend key/configuration is used for cultural brand ranking.

The catalog remains a timestamped research snapshot. Independent retailer page checks timed out during collection; structural URL validation does not prove every link is currently reachable. Photography reuse permissions are separate from data access.

## Validation

Tests cover constraints, owner separation, server-persisted feedback, actual Qloo seed parameters, reference-bridge ranking, deleted-image exclusion, graceful Qloo/catalog failures, account-scoped outbox recovery, stale acknowledgement protection, and the initialization/online-event race. Live browser QA uses an isolated account, the real 1,500-product snapshot and live Qloo. Its reference-analysis observations are a synthetic fixture; it does not claim a new end-to-end vision-model evaluation. That account and its uploaded reference are removed afterward.
