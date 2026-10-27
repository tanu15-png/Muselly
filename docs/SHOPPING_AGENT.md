# Shopping agent

The `/shop` request box uses `POST /api/shop/agent`, a bounded server-side agent
over the saved retailer catalog. It never scrapes, buys or invents products.
The direct search endpoint remains available for My likes.

## Tools and decisions

1. Read the authenticated customer's questionnaire signals, cultural feedback,
   fashion notes, current reference analysis and shopping feedback.
2. Gemini interprets the request into validated categories and soft preferences.
   Only supported listing terms are accepted. Cultural entity names alone never
   establish clothing attributes. An unusably vague request gets one question.
3. Qloo retrieves brand affinities from verified cultural entity IDs. Only brands
   actually present in the catalog contribute to ranking.
4. Search under explicit hard constraints; measure matches, brand variety and
   Qloo-connected candidates.
5. Gemini chooses a bounded next action: finish, expand Qloo from 50 to up to 150
   brand candidates across at most three pages of 50, or diversify near-leading
   matches. Expansion reuses the first-page cache, deduplicates entities, stops
   at the last page, and retains successful pages if a later request fails.
   One adaptive step is allowed.
   The server checks that the selected tool is applicable.
6. Empty searches can run a read-only counterfactual budget/color check. Suggested
   alternatives never appear as if they met the original constraints.

If Gemini is unavailable, supported-term interpretation and deterministic tool
selection remain available with a visible notice. If Qloo is unavailable, the UI
states that results use other preferences. This is degraded mode, not a Qloo discovery.

## Corrections and constraints

The follow-up field retains the previous request. Explicit numeric budgets,
category/color changes and exclusions are parsed server-side. Model output cannot
raise a budget. “More floral” is a soft preference; “without red” is a hard
exclusion. “Cheaper” promotes less expensive matching items. An explicit “yes” to
a specific saved budget suggestion authorizes that exact new ceiling.
Likes/dislikes continue to use the existing durable feedback queue.

The agent ranks eligible items by the latest explicit correction, a lower-price
band when “cheaper” is explicitly requested, listed occasion fit, and the request's
interpreted clothing preferences. Only then can saved taste and Qloo affinity distinguish
items. Alternatives such as several preferred colors are grouped rather than
requiring an item to contain every color. A new explicit attribute replaces an
older conflicting attribute of the same kind; price constraints are retained.
The request interpreter receives the request and conversation, while saved fashion
directions remain in personalization rather than being copied into request intent.
A budget ceiling alone never activates cheapest-first ordering. The direct
one-pass search remains unchanged for comparison and My likes.

### Taste-match percentage

Each eligible item includes `taste_match`, an estimated agreement score, not a
probability of customer satisfaction. Available signals have relative weights:
Qloo brand connection 30, best confirmed fashion direction 30, questionnaire
preferences 15, similarity to likes 15, and follow-up preferences 20. Missing
signals are omitted from the denominator. Similar dismissed styles can reduce
the estimate by up to 15 points. With no usable taste evidence the value is null
and the UI does not invent a percentage. Price and request eligibility are separate.

Results sort by descending displayed percentage, then the existing relevance
score, price, and product ID. Agent brand diversification occurs only within equal
percentages. The browser preserves descending percentages when appending pages.

For agent results, the percentage is conditioned on the request hierarchy above:
successive intent tiers occupy ordered score bands, with the saved-taste score
ordering products inside a tier. A brand affinity cannot compensate for a missed
correction or weaker request fit. Exact priorities break rounded percentage ties,
and diversification cannot cross those priorities. Thus the badge remains in the
existing UI and is still a heuristic, not a probability or a score directly
comparable with the direct-search percentage.

Conversations are owner-scoped, revision checked, and expire after 24 hours.
Expired rows are removed during subsequent agent turns. A reload starts a new UI
conversation; saved taste and shopping feedback remain independent.

## Setup and progress

Apply `alembic upgrade head` (migration `0011_shopping_agent`). Existing Gemini,
Qloo, database and catalog settings are reused; no agent SDK is required.
The endpoint streams newline-delimited JSON `progress`, `result` and `error`
events. The browser shows actual server stages, not simulated timers.
Catalog prices remain snapshots; users confirm prices, sizes and stock at the retailer.

Regression tests cover constraints, Qloo expansion, owner isolation, stale
revisions, gap diagnosis, budget approval, streaming, corrections and saved feedback.
