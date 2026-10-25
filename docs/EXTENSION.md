# Muselly browser extension

The website owns the taste test, private inspirations, Style DNA, Qloo brand
exploration, and saved product bookmarks. Product prompts, retrieval from loaded
shopping pages, Qloo discovery, corrections, and save-only snapshots live in the
Manifest V3 Chrome/Edge extension under `extension/`.

## Download and install

**Get Extension** links to `GET /api/extension/download`, which creates a ZIP
from the shipped extension sources, icons, and README. It embeds the backend's
configured `APP_ORIGIN` into `config.js`, the host permission, and the allowed
website connection pattern. No credentials or environment files are packaged.
The installation page is `/extension`.

1. Extract `muselly-extension.zip` to a folder.
2. Open `chrome://extensions` or `edge://extensions` and enable Developer mode.
3. Choose **Load unpacked** and select the folder containing `manifest.json`.
4. Pin Muselly, click its toolbar icon, then **Connect Muselly**.
5. Sign in on the website if needed and explicitly choose **Connect extension**.

The ZIP downloads directly. Downloading cannot silently install a browser
extension. A normal one-click install needs a published store listing; none is
claimed or published by this implementation.

For local development, keep Vite and the Python API running with their existing
`/api` proxy. `APP_ORIGIN` defaults to `http://localhost:5173`. Use that same
origin when signing in and connecting. In production, serve/proxy `/api` at the
configured website origin before downloading the package. Re-download and reload
the extension after changing the website origin.

## Discover my style

The extension has one personalized shopping flow. Enter an item and occasion,
optionally with a budget, then choose **Discover brands & shop**. Current,
non-dismissed Qloo affinities lead the discovery section. The first three brands
are offered initially; **Explore beyond my usual style** offers the next three
saved Qloo discoveries. This uses provider order, not a new diversity model.
No Qloo calls happen merely by opening the panel or searching retailers.

**Update my Qloo discoveries** explicitly runs enrichment. The five most recently liked product brands
join stated favorite brands and supported cultural interests as resolution
inputs. Unknown brands remain unresolved; there is no invented affinity. Changes
to liked brands mark the prior enrichment stale until an explicit update.

Brand searches offer a compact retailer chooser, with preferred shopping destinations first; these links do not establish that
a retailer stocks a brand, can deliver it locally, or meets a budget. Open a
retailer, click the Muselly toolbar icon on that tab, then **Find my favorites
on this page**. Only up to 100 loaded cards are ranked. Scroll and repeat to
consider more products. The extension does not rearrange the retailer page.

Explicit search constraints and saved dislikes filter candidates. Saved taste,
current inspiration-analysis attributes, product corrections, and current Qloo
brand affinities shape ranking. Brand names are normalized for case, spaces,
and punctuation before comparison. Provider rank contributes a bounded boost;
it is not a purchase probability. The explanations distinguish listed product
evidence from Qloo brand discoveries. Product images are not visually compared.

## Help me get closer

Each result offers **More like this**, **Not my style**, **Too expensive**,
**Wrong shape**, and **Wrong color**. Corrections are authenticated, persistent,
and owner-scoped. The latest correction replaces the prior one for that product.
Rejected products stay hidden until corrections are reset. The most recent 50
corrections influence similar items through listed color, construction, fit,
brand, and same-currency price evidence. Missing attributes are not inferred.
Price feedback downranks products at or above the rejected price; it does not
silently change the explicit budget. Positive feedback supplies additional brand
inputs on the next explicit Qloo update.

After a correction, the worker reranks the same candidates held in trusted
session storage for the connected owner. If reranking fails, the correction
remains saved and the panel asks the user to rank again. **Reset my corrections**
clears only the current owner's corrections. Reconnect after session expiry.
Product bookmarks remain separate from preference feedback.

## Save inspirations

Snapshots are save-only. **Take snapshot** lets the user select a visible region,
preview and crop it, then choose **Save inspiration to Muselly**. Uploading a
PNG, JPG, or WebP under 10 MB is also supported. Saving puts the image in the
existing private inspiration library; update Style DNA analysis on the website
to include new images in saved taste signals. There is no Find similar action
or extension image-description endpoint.

The query, retailer links, and results are retained per connected account in
trusted extension local storage. Tokens and reranking candidates stay in session
storage. Disconnect clears the workspace and session. Restored results are
labelled as saved; rank again for current prices, preferences, and stock context.
Retailer metadata is incomplete: sizes, delivery, stock and checkout prices
need store confirmation. Unknown prices are excluded; currency conversions use
the existing dated ECB feed.

## Setup for corrections

Run `uv run alembic upgrade head` from `backend/` to apply migration
`0006_product_feedback`, then restart the API and reload the extension. PostgreSQL
RLS and browser-role revocations protect the feedback table, following the
existing private application-table pattern. Tests use isolated SQLite databases;
no production migration is run automatically.

## Connection and permissions

The side panel creates a random, five-minute nonce and opens
`/extension/connect?extension_id=…&nonce=…`. The signed-in user approves sharing
the current access session with that installed extension. The website sends it
directly with Chrome's external messaging API. The worker accepts only its
configured website origin, a top-level sender, the live nonce, and a session
independently verified by `/api/auth/me`. Nonces are consumed after verification.
No password or refresh token is transferred. Access tokens are kept in trusted
extension session storage and never passed into retailer scripts or product DOM.

Permissions are `activeTab`, `scripting`, `storage`, and `sidePanel`, with host
access only for the configured Muselly origin. No `<all_urls>`, persistent
retailer host permissions, browsing-history permission, automatic content script,
background screenshot, remote executable script, or retailer login is used.
The worker rejects privileged messages from retailer content scripts. The side
panel renders text with DOM `textContent`, not retailer/model HTML.

## API and database

- `GET /api/extension/profile`: saved preferences and current Qloo discoveries.
- `POST /api/extension/search`: personalized brand searches and generic retailer links.
- `POST /api/extension/rank`: rank up to 100 loaded product records.
- `POST /api/extension/feedback`: save the latest correction for a product.
- `DELETE /api/extension/feedback`: clear the owner's corrections.
- `GET/POST /api/extension/saved`: list/create product bookmarks.
- `DELETE /api/extension/saved/{id}`: remove a bookmark.
- `GET /api/extension/download`: credential-free installable ZIP.

The existing authenticated onboarding image endpoint saves inspirations.
The existing enrichment POST explicitly refreshes Qloo discoveries. Enrichment
reads and searches do not trigger provider generation. Corrections and bookmarks
use separate private tables, protected by owner-scoped backend queries.

## Verification

Regression tests cover private corrections, repeat ranking, price feedback,
normalized Qloo brand matching, brand search links, exploration, liked-brand
inputs to enrichment, save-only snapshots, and worker/panel behavior.
Run backend pytest and frontend Vitest after installing platform dependencies.

## Store permission troubleshooting (extension 0.2.1)

If Find my favorites asks for toolbar access repeatedly, download the latest ZIP,
replace the installed extension files and reload it in chrome://extensions or
edge://extensions. Confirm version 0.2.1. In the panel, open **Store access**,
choose the retailer and click **Allow this store**. Accept the browser permission
prompt, switch to that retailer's product results tab, then rank again.

Only the selected supported retailer is requested. Optional host permissions
persist until revoked in browser extension settings. No products are read until
an explicit ranking action. The Muselly dashboard itself is not a retailer page.
Snapshot capture still requires the toolbar gesture on the active tab.
