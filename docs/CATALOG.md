# Hackathon catalog

The saved snapshot contains **6,098 women's clothing listings** across 15 supported categories:

- Myntra: 2,500 listings, 482 brands.
- AJIO: 1,542 listings, 261 brands.
- H&M India: 1,646 listings from H&M.
- Nykaa Fashion: 410 listings, 118 brands.

There are 738 distinct brand names overall. The price mix is 2,669 listings below ₹1,000,
2,090 from ₹1,000–₹2,499, and 1,339 at ₹2,500 or above. These are listing snapshots,
not live checkout quotes.

## Source selection and spending

The original target was 2,500 products each from Myntra, AJIO, SHEIN India and Nykaa Fashion.
SHEIN India did not have a verified compatible collection route in the tested setup. A generic
public-page collector was unavailable to the account; direct public requests were rejected.
Global SHEIN results were excluded because their market, currency and availability do not
establish Indian shopping options. H&M India passed a 20-item pilot and replaced that source.

The working AJIO and Nykaa routes were tested on 20 products before larger collection.
An initial empty AJIO route and an unrelated Nykaa result were rejected. The final routes use
AJIO listing URLs and Nykaa's plain search URLs, with explicit downstream gender/category checks.

Collection stopped at approximately **$9.78 total Apify account usage**, including approximately
$2.71 used before this expansion. The expansion consumed approximately **$7.07**. About $0.22
was left as a margin under the user's $10 ceiling; no further collection is scheduled.

Every batch stores its run ID and input so it can resume without creating a duplicate run.
Before starting a run, a shared lock reserves its maximum charge against the remaining budget.
Completed runs retain their reservation until Apify reports their dataset billing events as
accounted for; a successful run status alone is insufficient because billing can be delayed.

## Validation and identity

- Women-only source evidence: Myntra gender, AJIO breadcrumbs, Nykaa category/name evidence,
  and H&M's Indian locale plus ladies-category metadata. Men's, children's and pet clothing
  are excluded, as are unsupported clothing categories.
- Positive finite INR prices, supplied MRP consistency and source-host URL checks.
  Conditional coupon prices are not substituted for the ordinary listing price.
- Each included image passed an actual bounded download and Pillow verification. Successful
  cached checks were reused; transient timeouts received one retry. The final check rejected
  26 image candidates. Validated surplus Myntra items beyond its 2,500 target were not included.
- Canonical product URLs must match the retailer and source identifier. H&M links must use
  the Indian storefront. Images are limited to the expected retailer CDN hosts.
- Duplicate source IDs and canonical URLs are removed. IDs are scoped as `ajio:...`, `nykaa:...`
  and `hm:...`; existing numeric Myntra IDs and all original 1,500 Myntra links are retained.
- Similar names do not prove that garments are identical. Cross-store offers are retained
  separately rather than falsely merged. The count is distinct source listings, not a claim
  of 6,098 globally distinct garment designs.

Product URL structure is validated, but loading every retailer page, delivery to each postcode,
current prices, sizes and checkout have not been verified. The customer confirms these at the store.

## Runtime and submission

Customer searches filter and rank `backend/data/multi-retailer/catalog-products.json`.
Gemini interprets the request; Qloo supplies cultural brand connections. **Shopping never calls
Apify.** The UI uses each item's real retailer label and direct product link. H&M images use a public,
catalog-bound backend delivery route because direct CDN images failed in the tested browser.
It forwards no credentials, follows no redirects, validates raster image bytes, bounds each
download to 8 MB and uses a 32 MB memory cache. Ranking priorities,
Qloo weighting, correction handling and private feedback behavior are unchanged.

Raw collection files and account/run details remain in ignored `backend/data/`.
The submission archive is `assets/catalog/muselly-catalog.zip`; it contains only:

- `catalog-products.json`
- `validation-summary.json`
- `manifest.json`, with file checksums and counts

After cloning, run this from `backend/`:

```bash
uv run python tools/install_catalog.py
```

Installation uses the bundled snapshot and makes no network/API call. The legacy
`MYNTRA_CATALOG_PATH` environment override still works; its default is now the combined snapshot.

Collection tools are separate manual preparation commands. Do not run them merely to start,
test or demonstrate Muselly. No automatic refresh or recurring Apify job was added.

## Verification

With the same deterministic request filters, the office request under ₹2,000 grew from 707
eligible listings to 3,073; floral midi dresses under ₹1,500 grew from 12 to 78; relaxed cotton
tops under ₹1,000 grew from zero to six; vacation dresses under ₹3,000 grew from 96 to 915.
These counts establish improved catalog coverage, not proven customer preference or satisfaction.

An isolated real-Gemini/Qloo browser rehearsal checked requests, corrections, budget gaps,
mobile layout, source-specific links and saved likes from all four retailers after reload.
Separate browser checks confirmed images render from every source. The temporary account
and its upload were deleted afterward. The archive installation was checksum-verified and
all original 1,500 Myntra identifiers/links were preserved.
