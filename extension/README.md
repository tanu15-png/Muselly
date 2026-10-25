# Muselly Chrome extension

1. Extract the downloaded ZIP into a folder.
2. Open `chrome://extensions`, enable **Developer mode**, choose **Load unpacked**,
   and select the folder containing `manifest.json`.
3. Pin Muselly. Click its toolbar icon to open the side panel, choose **Connect
   Muselly**, sign in on the website if needed, and approve **Connect extension**.
4. Describe what you want, including an occasion and budget. Choose **Discover
   brands & shop** to explore Qloo discoveries, then open a retailer search.
5. Click the Muselly toolbar icon on that retailer tab, then **Find my favorites
   on this page**. Scroll and repeat to consider more loaded products.
6. Refine results with **More like this**, **Not my style**, **Too expensive**,
   **Wrong shape**, or **Wrong color**. Corrections persist privately; reset them
   any time. Update Qloo discoveries explicitly to include liked product brands.
7. **Explore beyond my usual style** shows the next saved Qloo brand discoveries.
   Brand search links do not verify retailer stock, delivery, or affordability.
8. **Take snapshot** or upload an image, crop the preview, and **Save inspiration
   to Muselly**. Snapshots only save inspirations. Update Style DNA on the website
   to incorporate new images. Product **Save to Muselly** stores a bookmark.

This development package is not a Chrome Web Store install. Downloading does not
automatically install it. No retailer passwords are requested. Credentials stay
in trusted extension session storage and expire with the website access token;
reconnect when prompted. Prompts/results are retained locally for your connected
account. Disconnect clears the local workspace. No background page scraping,
automatic screenshots, remote code, or access to all browsing history is used.

The included page adapters target Myntra, Amazon India, AJIO, Flipkart, Nykaa
Fashion, SHEIN India, and the four connected brand stores. Layouts change and
some pages block extraction: the panel reports unreadable pages instead of
inventing products. Only loaded cards are considered. Sizes, checkout prices,
and stock need confirmation at the store. Ranking uses listed attributes, saved taste, corrections, and Qloo brand discoveries. It does not visually compare product images.

The website origin is embedded when downloaded from `/api/extension/download`.
For local source loading it defaults to `http://localhost:5173`; keep the website
and Python API running. For production configure backend `APP_ORIGIN` and serve
`/api` from that origin before downloading. Only the configured Muselly origin
may connect an account. Tokens never go to retailer content scripts.
