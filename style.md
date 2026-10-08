# Muselly --- Product Design System & Agent Style Guide

> **Purpose:** Keep Muselly's website, onboarding, taste dashboard,
> shopping results, and Chrome extension visually consistent. Every AI
> coding agent should read this file before building or modifying UI.

## 1. Design direction

**Identity:** Editorial fashion meets calm, intelligent shopping.
Muselly should feel like a premium fashion magazine with the usability
of a modern SaaS product.

**Keywords:** elegant, airy, feminine without being childish, minimal,
warm, curated, confident, personal.

**Reference:** The approved landing-page concept: ivory canvas,
high-contrast fashion serif, blush-pink accents, soft overlapping outfit
imagery, white product cards, delicate handwritten arrows and
annotations.

**Avoid:** neon gradients, dark dashboards, heavy glassmorphism,
excessive shadows, cluttered cards, cartoon icons, generic AI chatbot
aesthetics, and inconsistent component styling.

## 2. Design tokens

Use CSS variables rather than scattered hex values.

  Token              Value       Usage
  ------------------ ----------- ------------------------------------------
  `--bg`             `#FCFAF8`   Main page background
  `--surface`        `#FFFFFF`   Cards, menus, panels
  `--surface-soft`   `#F8F2F1`   Secondary surfaces
  `--ink`            `#211E22`   Headlines and primary text
  `--muted`          `#777078`   Descriptions and labels
  `--accent`         `#E88CA4`   Pink highlights, charts, selected states
  `--accent-soft`    `#FBE7ED`   Badges and subtle highlights
  `--border`         `#EAE4E3`   Hairline borders
  `--success`        `#497B61`   Confirmed positive states
  `--danger`         `#B44F59`   Errors and destructive actions

**Typefaces** - **Display and brand:** `Cormorant Garamond` or
`Playfair Display` (serif). Use for the logo, hero, editorial headings,
and occasional highlighted words. - **Body and UI:** `Inter` or
`DM Sans` (sans-serif). Use for inputs, buttons, product information,
filters, tables, and dense dashboard content. - **Handwritten
annotations:** `Caveat` (sparingly, only on landing-page decorative
notes). - Load fonts through a supported web-font service with
appropriate fallbacks. Do not distribute font files.

**Typography** - Hero: `clamp(3.2rem, 6vw, 6rem)`, line-height
`0.98–1.05`. - Section headings: `clamp(2rem, 3.5vw, 3.5rem)`. - Card
headings: `1.1–1.4rem`; body: `0.95–1rem`; metadata: `0.8–0.875rem`. -
Prefer sentence case. Avoid uppercase except small eyebrow labels.

**Shape and spacing** - Spacing scale:
`4, 8, 12, 16, 24, 32, 48, 64, 96px`. - Buttons: fully rounded pills for
primary CTAs. - Cards: `16–24px` radius; inputs: `12–16px`. - Borders:
`1px solid var(--border)`. - Shadows: very soft and subtle; avoid large
dark drop shadows. - Desktop content width: `1200–1360px`; comfortable
gutters. - Plenty of whitespace. Use restrained asymmetry for editorial
sections, regular grids for shopping results.

## 3. Component rules

### Navigation

-   Left: lowercase serif wordmark **muselly**.
-   Center: `How it works`, `For you`, `Extension`, `FAQs`.
-   Right: outlined `Sign in` and dark `Get taste test` pill.
-   Sticky navigation may use a solid ivory background and fine bottom
    border.
-   On mobile: accessible menu with the same destinations and a visible
    taste-test CTA.

### Buttons

-   **Primary:** near-black background, white text, pill shape, subtle
    hover lift.
-   **Secondary:** white or transparent background, thin gray border,
    dark text.
-   **Accent:** blush background with dark or deep-rose text, reserved
    for special actions.
-   Provide visible hover, focus, disabled, and loading states. Use
    descriptive verbs.

### Cards and imagery

-   Use real-looking editorial outfit imagery with neutral backgrounds,
    natural lighting, and consistent crop ratios.
-   Product cards: image (3:4), item name, retailer, price, optional
    match indicator, and a clear retailer link.
-   Never imply fabricated prices, availability, or match scores are
    real; mock data must be labeled.
-   Avoid arbitrary logo assets or distorted brand marks.
-   Save/inspiration cards use the same corner radii, borders, and
    typography.

### Inputs and filters

-   Spacious search bar with conversational placeholder: "Find a
    farewell dress under ₹3,000..."
-   Retailer filters are selectable chips with clear active states.
-   Taste preferences use chips, small bar visualizations, or simple
    editable controls.
-   Form labels remain visible; placeholders are not substitutes for
    labels.

### Icons and motion

-   Use one icon family throughout (Lucide recommended), with consistent
    stroke widths.
-   Use restrained transitions around `150–250ms`; avoid distracting
    parallax.
-   Respect `prefers-reduced-motion`.

## 4. Screen-by-screen visual guidance

### A. Landing page

-   Preserve the approved composition: **left editorial headline +
    description + taste-test CTA**, **right layered fashion collage**.
-   Headline: **"Discover fashion that feels like *you*"**, with *you*
    in blush-pink italic serif.
-   Supporting copy: "Upload your inspirations, take a quick taste test,
    and let our AI understand your style. Get personalized outfit
    recommendations from your favorite shopping sites --- anywhere on
    the web."
-   Decorative handwritten annotations (use sparingly and only here):
    -   "Turn your Pinterest inspo..."
    -   "...into a personalized taste profile"
    -   "Start with a quick taste test and upload your inspo images"
    -   "Shop your taste on any website"
-   Show inspiration photos, a Style DNA preview, retailer product
    cards, and subtle pink doodles/arrows.
-   CTA: `Get taste test →`.
-   Subsequent sections: How it works, For you, Extension with
    `Get Extension` CTA, FAQs.

### B. Sign-in and taste test

-   Calm, guided onboarding; one focused question per step.
-   Use visual image-choice grids, preference chips, and progress
    indicator.
-   Let users skip optional questions and upload inspiration
    images/screenshots.
-   Pinterest connection may be offered as an optional route **only when
    authorized and supported**; otherwise provide upload or
    extension-save alternatives.
-   Show privacy/consent messaging for uploaded images and connected
    data.

### C. Style DNA dashboard

-   Use editorial greeting and a compact overview.
-   Include visual preference breakdown, dominant palette, saved
    inspirations, editable preferences, and a prominent `Shop my taste`
    search.
-   Make insights understandable; do not imply Qloo directly identifies
    fabrics/colors from photos.
-   Prefer light surfaces and airy cards; avoid overwhelming analytics
    panels.

### D. Product search and results

-   Search-first layout with natural-language query, budget, category,
    occasion, and retailer filters.
-   Show results as responsive product cards (4 columns on large
    desktop, 2 on tablet, 1--2 on mobile).
-   Include image, product title, price, retailer, reason for match, and
    `View on retailer`.
-   Show match scores **only when your ranking system actually computes
    them**; otherwise use qualitative explanations.
-   Clearly distinguish verified product data from inferred style
    traits.
-   Empty, loading, error, and no-results states must be designed, not
    omitted.

### E. Chrome extension

-   **Same brand, more compact UI**: ivory background, serif heading,
    sans-serif controls, pink highlights.
-   Primary actions: `Analyze this item`, `Find similar`,
    `Filter by my taste`, `Save to Muselly`.
-   Popup width approximately `360–400px`; ensure scrollable content and
    readable labels.
-   On-page overlays should be minimal, dismissible, and never obscure
    checkout or important retailer controls.
-   Sidebar recommendations should link to the original product page.
-   Never assume extension support on every website; provide graceful
    unsupported-page states.

## 5. Responsive and accessibility rules

-   Design mobile-first; test at roughly `375px`, `768px`, `1024px`, and
    `1440px`.
-   Collapse hero collage carefully on mobile without covering text or
    buttons.
-   Maintain WCAG AA text contrast where possible, keyboard navigation,
    visible focus, alt text, and semantic HTML.
-   Do not use color alone to indicate selected filters or match
    quality.
-   Buttons and touch targets should be comfortably tappable (aim for at
    least `44×44px`).
-   Avoid horizontal overflow and text clipping.

## 6. Content voice

Muselly speaks like a thoughtful personal stylist: **warm, concise,
helpful, never pushy**.

-   Prefer: "Find pieces that feel like you."
-   Prefer: "Why this matches your style."
-   Prefer: "Save to your inspirations."
-   Avoid: "Our revolutionary AI algorithm delivers unprecedented
    personalization."
-   Explain recommendations with concrete reasons (cut, palette,
    silhouette, stated preferences).
-   Avoid claiming the app knows a user's identity or taste with
    certainty; let them edit and correct the profile.

## 7. Agent implementation rules

1.  Read this file and the product README before creating screens.
2.  Reuse shared components and tokens; **do not invent a new visual
    language for each page**.
3.  Keep Qloo, vision analysis, product retrieval, and ranking
    responsibilities separate in UI copy and code.
4.  Use realistic placeholder data only when labeled; never invent
    retailer inventory or API output.
5.  Build all states: loading, success, empty, error, unauthenticated,
    and unsupported.
6.  Keep visual consistency between web app and extension while
    respecting different screen sizes.
7.  Review each screen against the approved landing-page reference
    before finalizing.
8.  Prefer simple, maintainable components over decorative complexity.

## 8. Acceptance checklist

-   [ ] Serif editorial headings + clean sans-serif interface throughout
-   [ ] Ivory, ink, blush, and subtle borders match the tokens
-   [ ] Primary CTAs and navigation look consistent
-   [ ] Product imagery, card ratios, and spacing are coherent
-   [ ] Website and extension clearly belong to the same brand
-   [ ] Mobile layout, keyboard access, focus, and empty states work
-   [ ] Product prices, retailer links, and match claims are grounded
-   [ ] No unrelated visual trends or inconsistent one-off components

**Design principle:** *Muselly should feel curated before it feels
technical.*
