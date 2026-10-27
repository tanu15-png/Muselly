# Muselly: a three-minute customer demo

**Story:** “Help me find an outfit that feels like me, and let me correct it.”

Prepare a signed-in account with its questionnaire, reference images and a few genuine cultural choices already saved. Start on the dashboard; avoid spending the presentation filling in twenty questions. Keep the shopping page ready in a second tab.

## 0:00–0:35 — Show where taste comes from

Show the mixed cultural discovery deck, including music. Save a discovery with **Use as fashion inspiration**, then open **Your direction** and enter:

> I like floral prints, soft colors and relaxed cotton pieces.

Say: “Qloo connects my interests to cultural discoveries. I explain what a discovery means for my clothes, so Muselly does not assume that liking an artist means liking their wardrobe.”

Briefly show the color/pattern analytics and the accessible inspiration library. These visual attributes come from the reference-image analysis, not from poster colors.

## 0:35–1:20 — Make the initial request

In **Shop your taste**, enter:

> Everyday office outfit under 2000

Let the progress updates run. Point out the budget and the actual **Qloo-connected brands in catalog** indicator if it is present.

Say: “The agent reads my request and saved taste, queries Qloo for brand connections, and ranks real products from our 6,098-item catalog across Myntra, AJIO, Nykaa Fashion and H&M India. My explicit request and budget take priority.”

Only attribute an individual product to Qloo when its returned evidence supports that claim. A Qloo query does not mean every displayed item has a Qloo brand connection. If no relevant brands resolve, acknowledge that rather than claiming a boost.

## 1:20–2:05 — Correct the agent

Enter:

> Less formal, more floral

Show that the shortlist changes toward floral pieces while the ₹2,000 ceiling remains. Compare the actual product pictures, not just the displayed percentages.

Say: “I can steer the agent in ordinary English. Qloo personalizes suitable options; it cannot override my correction.”

The taste-match percentage is an agreement score from available signals, not a probability that the customer will like an item.

## 2:05–2:35 — Save and shop

Click **I like this** on one suitable item. Open its retailer link in a new tab. Choose a Myntra result if demonstrating that specific store.

Say: “My choice is saved for future personalization. Muselly helps me discover; the retailer handles current availability, size selection and checkout.”

Do not claim the catalog price is a live checkout quote. Do not place an order during the demo.

## 2:35–3:00 — Make the differentiator clear

Say: “Muselly combines Qloo's cultural connections, my own explanation of my style, and an agent that responds to corrections—then connects that taste to real products.”

If time allows, show the existing same-request Qloo-on/off comparison. Explain that it isolates live brand affinity while retaining the same saved preferences. Different rankings demonstrate influence, not proven customer satisfaction.

## Rehearsal checks

- Backend and frontend running; Gemini billing and Qloo available.
- Questionnaire and reference images prepared; pending feedback synced before analytics.
- Run the exact request and correction once before presenting. Provider responses and recommendations can vary.
- Check the chosen Myntra link in the presentation browser. Retailer access may differ from automated access.
- Keep screenshots from a real rehearsal available; clearly label them if presenting a recorded result after a network failure.
- Keep API keys, account credentials and browser developer tools off screen.

Google's account-selection/consent screen requires a manual rehearsal; automated QA verifies the Google OAuth handoff separately.

## Earlier 1,500-item rehearsal — 26 October 2026

The isolated browser rehearsal completed real email sign-in, all twenty questions, five image uploads, Gemini analysis, all four Qloo categories (including eight artists), feedback replay after reload, analytics sync, an autosaved fashion note, both shopping turns and saved shopping likes. The temporary account and its uploads were removed afterward.

- The blocked-network cultural choice advanced in 102 ms and survived reload.
- The office request returned 707 eligible products; Qloo resolved six catalog brands, with 35 eligible products from those brands. None reached this rehearsal's leading shortlist: request fit took priority. The demo should show the Qloo indicator and confirmed cultural fashion note, rather than claim that Qloo boosted the first product.
- “Less formal, more floral” returned twelve floral items in the top twelve and retained the ₹2,000 ceiling. The first was a SURHI floral cotton kurta, catalog price ₹332; its evidence matched the saved note for *Me Before You*.
- The exact Myntra destination was requested successfully by the browser, but the retailer navigation failed with `ERR_HTTP2_PROTOCOL_ERROR`. Retailer page loading, current availability and checkout remain manual checks. The app's product URL is valid in form; this rehearsal does not establish that the listing is currently purchasable.
- Validation: 152 frontend tests, 36 focused backend tests, and the production build passed.

Screenshots from the real rehearsal: [initial request](../test-results/customer-journey/initial-shop.png), [analytics](../test-results/customer-journey/live-visual-analytics.png), [saved item on mobile](../test-results/customer-journey/shopping-mobile.png).


## Final four-retailer check — 26 October 2026

The submission snapshot has 6,098 saved listings: Myntra 2,500, AJIO 1,542, H&M India 1,646,
and Nykaa Fashion 410. SHEIN India was excluded after source checks; H&M India replaced it.

A separate isolated-account browser check used a real Qloo seed, an explicit fashion note and
real Gemini interpretation. “A floral dress for a Switzerland vacation under 3000” returned
471 eligible listings, including 17 from Qloo-connected brands. The top twelve were Qloo-connected
H&M products in this rehearsal. “Cheaper and without red” retained the ₹3,000 ceiling, excluded
red and changed the leading results to lower-priced AJIO items. This demonstrates a visible Qloo
contribution while a customer correction can take priority; it does not establish customer satisfaction.

The check also verified budget-gap diagnosis, mobile layout, retailer-specific links and saved
likes from all four retailers after reload. Representative images from all four stores rendered
in the browser after adding bounded H&M image delivery. The temporary account and its uploaded
image were removed afterward. Retailer checkout, delivery and live availability remain manual checks.

Do not run collection tools for the presentation. Install the bundled snapshot and use the saved
catalog. See [catalog preparation](CATALOG.md).
