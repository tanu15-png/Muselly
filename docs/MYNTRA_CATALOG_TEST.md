# Myntra catalog verification — 25 October 2026

This is an offline data-source test, not a shopping implementation or a licensed product feed. No application routes, database tables, dashboard sections, or shopping UI were changed.

## Result

The initial 20-product women's dresses pilot passed record validation and primary-image checks. The resulting catalog contains 200 distinct women's products: 40 dresses, 40 tops, 30 trousers, 30 kurtas, 30 co-ords and 30 jackets. It covers 93 brands and 31 primary colors; listing prices range from INR 225 to INR 1,899. These counts describe this sample, not Myntra's full assortment.

All 200 records have product IDs, names, brands, numeric INR prices, collection timestamps, correctly formed Myntra product URLs, and primary images that fetched successfully over HTTPS and decoded as images. Gender and exact category are checked before accepting records. The first broad tops batch included 27 thermal tops; it was replaced using Myntra's explicit Tops category filter. Each accepted tops record is category Tops.

## Important findings

- The collector returned HTTP image URLs. The equivalent HTTPS URLs were independently fetched and image-decoded before inclusion. Image files are not copied into the app.
- The collector's summary `inStock` was false for all 200 accepted products, even though its detailed inventory entries contained available sizes. The normalized catalog retains that original flag for audit, derives `available_sizes_observed` only from explicit inventory evidence, and labels the result `available_in_listing`. Listed size names do not imply all sizes are in stock. Missing evidence means unknown.
- Three ordinary direct product-page requests timed out. Therefore the product URLs are structurally checked, not independently confirmed live page loads. Prices are current collector listing snapshots, not independently verified product-page or checkout prices. Coupons, size-specific prices, postcode delivery, and subsequent stock changes remain unverified.
- API access does not establish rights to republish product photography. This test does not assert image-display permissions or Myntra authorization.

## Local files

`backend/data/myntra-verification/` is ignored by Git and contains:

- `pilot-products.json` and `pilot-validation.json`: accepted pilot records and checks.
- `catalog-products.json`: 200 normalized records for future testing.
- `catalog-products.csv`: the same records in spreadsheet-friendly form.
- `catalog-validation.json` and `catalog-image-checks.json`: validation results and image dimensions.
- Per-run inputs, IDs, statuses and original output, including the superseded thermal-heavy tops batch for provenance.
- `pilot-page-checks.json`: the three failed independent product-page checks.

The provider is `shahidirfan/myntra-product-scraper` on Apify. Eight runs were used, including the pilot and tops refinement. Their completed-run API responses reported USD 0.04 in total `usageTotalUsd` at verification time; this is a reported snapshot, not an invoice or a forecast. Pilot actor-charge limit was USD 0.15; subsequent runs used USD 0.10 each. No plan upgrades or schedules were created.

## Reproducing validation

The token is read from `APIFY_API_TOKEN` in `backend/.env`, sent in an authorization header, and never included in command text or stored exports.

From the repository root:

```powershell
.\backend\.venv-win\Scripts\python.exe -u backend/tools/myntra_probe.py validate-pilot
.\backend\.venv-win\Scripts\python.exe -u backend/tools/myntra_probe.py collect-200
```

Existing run IDs are reused so rerunning polls existing jobs instead of creating duplicate billed jobs. Image validation still performs fresh image requests. This does not refresh old product snapshots; a future fresh collection needs separate run manifests. Do not delete run manifests just to retry an uncertain start request.

The standalone normalizer has five tests covering HTTPS conversion, original-record preservation, inventory semantics, women/category/domain validation, and invalid/non-finite prices.

Sources: [collector documentation](https://apify.com/shahidirfan/myntra-product-scraper), [Apify run API](https://docs.apify.com/api/v2/actors-runs-post).
