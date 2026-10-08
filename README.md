# Muselly

**Your taste, everywhere you shop.**

Muselly is an AI-powered fashion discovery platform that learns a user's style from a visual taste test and inspiration images, then helps them find matching products across supported shopping sites. A companion Chrome extension brings that taste profile into everyday browsing.

## Local setup — Phase 1

The frontend uses **React and JavaScript with Vite**. The backend uses
**Node.js**, with no backend dependencies required for Phase 1. Use Node.js
22.12 or newer (Node.js 24 recommended).

Run the frontend from its own directory:

```bash
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite (normally `http://localhost:5173`).
The backend runs independently in a separate terminal:

```bash
cd backend
npm run dev
```

To serve the production frontend build through Node.js, first build it
from `frontend/`:

```bash
npm run build
```

Then run `npm start` from `backend/`.

Open `http://localhost:3000`. Set `PORT` to change the backend port.
`GET /api/health` returns the backend health status. Run `npm test` from
`backend/` for the backend request-handler checks. The repository root has
no npm package or run scripts; each app owns its dependencies and scripts.

```text
frontend/
  package.json
  index.html
  src/
    main.jsx          # React mounting entry point
    App.jsx           # Application UI and page selection
    components/       # Shared UI components
    styles/           # Shared design tokens and styles
  public/
backend/
  package.json
  server.js
  server.test.js
```

**Implemented:** responsive landing page, section navigation, mobile menu,
FAQs, a visual taste-test entry preview at `/taste-test`, and a sign-in
entry page at `/sign-in`. The extension CTA shows **Coming soon**.

**Scope:** authentication belongs to Phase 2; the full taste test and
image uploads belong to Phase 3. The taste preview supports selecting
and revising aesthetics, with choices held only in React page state.
It does not save an account or generate an AI profile. Retailer names,
Style DNA, and extension examples are labeled as planned or illustrative.

Shared tokens live in `frontend/src/styles/tokens.css`; shared UI
components live in `frontend/src/components/`. The supplied images from
`assets/images` are copied to `frontend/public/images` for serving. Fonts
load from Google Fonts with local fallbacks, without distributing font
files. The approved composition is in `assets/references/landingpage.png`.

**Verification:** the production build and Node.js request-handler tests
pass. Live browser testing is still needed at 375, 768, 1024, and 1440px;
the implementation environment blocks local listening sockets. Check
the mobile menu, all navigation anchors, FAQs, selection/continue/edit,
keyboard focus, and horizontal overflow at those sizes.

## Product journey

```text
Landing page → Sign in → Taste test + inspiration images
            → Style DNA dashboard → Describe what to shop for
            → Choose retailers → Personalized product results
            → Open product on retailer's website

Chrome extension ↔ Saved Style DNA + inspiration library
```

### 1. Landing page and onboarding

The landing page introduces Muselly with **“Discover fashion that feels like you.”** Its navigation includes **How it works · For you · Extension · FAQs**, plus **Sign in** and **Get taste test** actions. The Extension section includes a **Get Extension** button.

After signing in, users complete a short visual taste test (preferred outfits, aesthetics, colors, silhouettes, and dislikes). They can also upload photos, screenshots, or Pinterest inspirations. Connecting a Pinterest account/board is a *future enhancement*, subject to API access and permissions; the MVP supports manual uploads and saving individual images through the extension.

### 2. Style DNA dashboard

Muselly analyzes the selected images and answers to generate an editable **Style DNA** profile:

- **Taste overview:** aesthetics, colors, silhouettes, materials, and preferred brands.
- **Taste graph:** visual connections between saved inspirations and supported style/brand affinities.
- **Inspiration library:** uploaded and saved images, with options to remove or organize them.
- **Taste analyzer:** explanations of recurring preferences and why suggested items fit.
- **Shopping search:** a natural-language prompt and saved searches/results.

The user can update their preferences at any time; the profile evolves as they add or remove inspirations.

### 3. AI-powered product search

1. User asks: **“Find me a farewell dress under ₹3,000.”**
2. Muselly extracts the occasion, item category, budget, and other constraints.
3. User chooses supported retailers (for example, Amazon, Flipkart, Meesho, Myntra, AJIO, Urbanic, or Savana).
4. The shopping agent retrieves available candidate products from integrated product sources, then ranks them using visual fit, taste affinity, and user constraints.
5. Results appear as **product cards on the Muselly dashboard**: image, title, price, retailer, taste-match estimate, and **Why it matches** explanation.
6. Clicking **View product** opens the original retailer listing; Muselly does not handle checkout.

**Important:** Retailer support depends on lawful, reliable product-data access. The MVP should integrate one or two working sources first, not promise complete catalogs across every site.

### 4. Chrome extension

The extension uses the same signed-in profile and supports three actions while the user browses supported sites:

| Action | Behavior |
| --- | --- |
| **Find similar** | Analyze a selected outfit/product and show similar options in the extension panel or Muselly dashboard. |
| **Filter by my taste** | Score and highlight products visible on a supported retailer's results page; optionally dim weaker matches. |
| **Save to Muselly** | Save a selected image or product to the inspiration library for future recommendations. |

The extension is a **browsing companion**, not a separate shopping account. Page filtering requires site-specific support and does not search a retailer's entire inventory.

### 5. AI and Qloo responsibilities

```text
Taste test + images ──→ Vision model ──→ Visual style attributes
                                            │
Supported brands/interests ──→ Qloo API ──→ Taste/brand affinities
                                            │
Shopping request ──→ Agent + product source ──→ Candidate products
                                            │
                          Ranking + explanations ──→ Recommendations
```

- **Vision model:** interprets images and extracts visible fashion attributes.
- **Qloo:** enriches supported entities and cultural/brand taste affinities; it does **not** directly recognize uploaded images or provide retail inventory.
- **Shopping agent:** interprets requests, chooses tools, retrieves products, and applies constraints.
- **Ranking layer:** combines visual similarity, Qloo-derived signals where available, and budget/occasion fit. Any displayed match percentage is Muselly's own estimated score, not an official Qloo score.

## Hackathon MVP scope

**Build now:** responsive landing page; authentication; visual taste test; image upload; Style DNA dashboard; natural-language search; one or two real product sources; ranked results with retailer links; basic Chrome extension for saving images and analyzing/filtering supported pages.

**Later:** full Pinterest account sync, broader retailer integrations, richer taste graph, collaborative shopping, outfit building, and more advanced personalization.

## Success criterion

A new user can **sign in → create their taste profile → search for an occasion-based outfit → compare personalized matches → open a retailer product**, then use the extension to save or evaluate another look without starting over.
