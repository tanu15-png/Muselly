# Expanded Myntra research catalog

This standalone collection is separate from the website. It adds no shopping interface, API route, application database data, or scheduled refresh. The earlier 200-product exports remain in `backend/data/myntra-verification/`.

## Completed result — 25 October 2026

The final JSON and CSV each contain exactly 1,500 distinct women's product IDs, with 100 products per category. The catalog covers 380 brands and 40 colors. Listed prices range from INR 222 to INR 9,985. The price-band totals are 750 budget, 450 midrange and 300 premium products.

All 1,500 accepted primary images passed HTTPS retrieval and image-format validation; the smallest accepted dimensions were 1,000 by 1,333 pixels. Six other image candidates timed out and were excluded/replaced. Every final record passed the numeric-price, supplied-MRP, exact-category, women-only and canonical Myntra product-URL checks. JSON and CSV row counts and product-ID uniqueness were checked independently after export. Listing names/descriptions supplied 37 distinct matched style keywords across the catalog.

All 15 independent ordinary HEAD requests (one selected product per category) ended in `ReadTimeout`. Therefore the catalog does **not** claim live Myntra-page reachability, independently confirmed product-page prices, or checkout availability. The direct links remain canonical URLs supplied by the collector, structurally validated against each product ID. No access-control workaround was attempted for these independent checks.

The saved completed-run statuses reported USD 1.0566 in total `usageTotalUsd` for this expanded dataset, including its reused premium-dress probe and the extra T-shirt batch. This is the provider's recorded snapshot, not an invoice or future-cost guarantee. The selection/normalizer tests passed (nine tests). No application code or shopping UI was changed.

## Collection and selection

The expanded output lives in the Git-ignored folder `backend/data/myntra-1500/`.

The plan targets 100 women's products in each of 15 categories: dresses, tops, shirts, T-shirts, jeans, trousers, skirts, shorts, kurtas, kurta sets, co-ords, sweaters, sweatshirts, jackets and blazers.

Within each category the target is 50 products at INR 200–999, 30 at INR 1,000–2,499, and 20 at INR 2,500–10,000. These are collection bands, not personalized spending recommendations. Sponsored results can ignore retailer search filters; actual returned gender, category and price are independently checked before selection. Unisex, men's and children's records do not qualify.

Selection favors varied brands, colors and explicitly stated listing style terms. `listing_style_terms` are keyword matches from product names/descriptions, not AI image interpretations or Qloo-derived clothing attributes. They must not be treated as customer-confirmed preferences.

Each accepted record must have a distinct Myntra product ID, a brand/name and collection timestamp, a finite positive numeric INR price within its band, and an HTTPS product URL on Myntra whose path ends in that product ID and `/buy`. Supplied MRP cannot be below the listing price. URL credentials, unexpected ports, query strings and fragments are rejected. Only primary images on the Myntra asset hostname qualify; equivalent HTTPS images are checked with an actual download and image-format validation, not merely URL presence.

The collector's summary `inStock` is unreliable in the tested output. It is retained for audit but is not trusted. Only explicit per-size inventory evidence populates `available_sizes_observed`; other sizes and postcode-specific delivery remain unknown.

## Validation limits

Prices are timestamped retailer listing snapshots obtained through the collector. Arithmetic/type/band validation does not establish current checkout prices, coupon eligibility, or future availability. Ordinary direct page access may time out or be restricted independently of whether a customer can open the product in their browser.

`myntra_link_check.py` samples one product per category with ordinary HEAD requests and records each result in `link-reachability.json`. It performs no bypass or proxy workaround. HTTP 200 establishes header-level reachability only, not product content, price or checkout validity. Non-200 responses and timeouts remain unconfirmed; they are not silently marked working.

API access and image availability do not establish photography reuse rights or Myntra authorization. No image files are published in the app by this collection.

## Files and commands

- `catalog-products.json` and `catalog-products.csv`: the final catalog, produced only after count, uniqueness, category and image gates pass.
- `validation-summary.json`: actual category/budget counts, brand/color counts, listing keyword counts, price range and provider-reported run charges.
- `collection-plan.json`: the exact planned queries and quotas.
- `image-checks.json`: successful/failed image checks with timestamps and dimensions.
- Per-batch run manifests and original outputs: provenance, duplicates, out-of-band ads and rejected gender/category records remain auditable.

From the repository root:

```powershell
.\backend\.venv-win\Scripts\python.exe -u backend/tools/myntra_expand.py
.\backend\.venv-win\Scripts\python.exe -u backend/tools/myntra_link_check.py
```

`APIFY_API_TOKEN` is read locally from `backend/.env` and sent only in an authorization header. Runs have actor-charge limits and saved IDs; rerunning resumes existing batches rather than starting duplicate jobs. Existing snapshots are not automatically refreshed. Up to two initial collection jobs run concurrently; image checks use six workers. The original premium-dress price-filter probe is reused as one source batch. Additional result ordering can fill a shortage of eligible records.

For a completed `selected-products.json`, `myntra_expand.py --export-only` rebuilds exports without starting collector jobs or rechecking images. The stored verification timestamps still apply.

Source: [Apify collector documentation](https://apify.com/shahidirfan/myntra-product-scraper).
