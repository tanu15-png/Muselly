# Cultural discovery and taste analytics

The dashboard shows one Qloo entity at a time. The deck always mixes artists, films, shows and books; the category selector has been removed. Reference images remain in the collapsible **My inspirations** library. Analytics is collapsed by default.

## Categories and failures

The saved run observed during diagnosis had artists and shows unavailable, while films and books succeeded. Repeating those exact inputs succeeded for all four categories. The old code discarded category errors, so the historical failure cannot be identified conclusively.

Categories run concurrently with independent request deadlines. Artist Insights requests allow 25-second HTTP timeouts within a bounded 60-second category budget; other categories use 12-second HTTP timeouts within 32 seconds. Failed categories automatically retry with bounded backoff, even before the first choice. Other posters remain usable. Each stores ready/unavailable state, error code/message, received/excluded counts, next offset and exhaustion. Resolution failures are distinguished from unsupported interests. Partial results are not treated as complete cache hits. A failed refresh preserves the previous successful run.

A live check of the updated pipeline with the saved inputs returned eight artists, eight films, eight shows and eight books. This is a point-in-time capability check, not an uptime guarantee.

## Sessions and feedback

- An explicit Start/Refresh prepares current image interpretation when possible and calls `POST /api/onboarding/culture` to create a saved run and session.
- `GET /api/onboarding/culture` restores the latest owner-scoped queue. GET never calls Qloo or Gemini.
- Displayed cards and choices first enter an account-scoped IndexedDB outbox. Prefetched cards are not counted as seen. Legacy single-action routes remain compatible, but the current UI sends batches.
- A short local transaction persists a choice and consumes its card atomically. The next poster appears without waiting for network acknowledgement. Events retain UUIDs and insertion order through retries/reloads. Pending choices continue working offline while buffered posters remain.
- Undo restores the card locally and queues a compensating event. Pending and acknowledged choices use the same ordered mechanism. Server history retains the undo; timeline charts exclude the undone action.
- `POST /sessions/{id}/batch` fetches the next offset per available category. An optional category selects a single stream. Refilled buffers exclude previous views and current feedback; Mix interleaves categories.
- After five new preference choices, active sessions can refresh their query with current feedback. The first few queued cards remain stable while new results are prepared. A low queue also triggers prefetch. Recovered music is interleaved into the mixed buffer; delayed refills preserve the currently visible local card. Pause prevents automatic poster fetches; pending choices continue synchronizing.
- Queue merges preserve feedback committed while network requests were in flight. Profile locks serialize local mutations. Network calls release database locks.
- Liked/fashion-saved entities become positive seeds; familiar and disliked entities are excluded, without treating familiarity as dislike. Positive seeds and wire exclusions are bounded; local seen/feedback checks still prevent repeats.
- Fetches have rate limits, leases, bounded automatic retries, and category exhaustion. The UI never promises an unlimited supply of relevant entities.

`0008_discovery_sessions` creates session, exposure and append-only event tables with owner foreign keys, Postgres RLS and no browser grants. Earlier feedback stays available; historical views cannot be reconstructed.

## Durable background synchronization

`POST /api/onboarding/culture/sessions/{id}/sync` accepts at most 50 ordered actions (shown, like, dislike, known, fashion, skip, undo). The frontend flushes around every two seconds or five choices, with one in-flight worker per mounted owner. The worker groups events by session, retries with backoff, and resumes on online/visibility events. UUID acknowledgements remove only accepted events. Failed or uncertain requests remain durable. No unload-only save is relied on.

The endpoint acquires the existing owner lock once, loads events/exposures/preferences in groups, commits one transaction and returns only acknowledgement IDs and a choice counter. It never rebuilds the full profile or calls Qloo. Unknown/unoffered entity IDs and cross-owner sessions are rejected. Offered records are retained across buffer replacements so delayed actions remain valid.

The local deck records consumed entities separately from pending events. Late/stale responses cannot resurrect acknowledged cards. Undo targets are ordered and validated; conflicting edits remain pending for attention rather than silently overwriting newer choices.

Each synchronization request checks that the current Supabase account matches the outbox owner. Logout/unmount stops that worker. Pending events remain isolated under the original account and are never posted with another account's token.

Opening analytics establishes a synchronization barrier before mounting the analytics component. If offline/sync fails, it shows a pending state and retry control, not stale totals presented as current. Background saves also run without opening analytics.

Verification: the real-browser test advanced a card in 76 ms during a deliberately held save, restored pending actions and the next card after reload, and blocked analytics until acknowledgement. A live artist query using saved inputs returned eight artists in about 14.7 seconds after the timeout change. These are point-in-time checks, not uptime guarantees.

## Analytics

`GET /api/onboarding/culture/analytics` is read-only and owner-scoped.

**Colors & patterns:** counts distinct matching reference images per attribute. Labels are case-deduplicated per image. Deleted/replaced images are excluded by ID and update timestamp. Approximate swatches and AI observations are labelled; questionnaire colors are shown separately. Clicking an attribute opens supporting images.

**Cultural taste:** distinct cards actually shown, current likes/dislikes/familiar/fashion counts per category, likes divided by likes plus dislikes with sample counts, Qloo tags attached to liked entities, and saved-action activity by UTC date. No rating yields an empty rate rather than zero. Familiarity is excluded from the denominator. Legacy preferences can exceed tracked views; the UI discloses when history began.

**Your direction:** image-observed colors, patterns and aesthetics alongside explicitly fashion-saved entities and their returned Qloo tags. These are complementary evidence sources, not inferred causal links. Poster colors are never used as clothing preferences.

## Provenance and scope

Questionnaire names resolve to actual Qloo entities. Image-derived aesthetics influence Qloo only through exact, unambiguous matches in supported fashion/style/aesthetic tag namespaces. Artwork comes from Qloo's returned image URL or a category placeholder; it is not generated. Provider image availability does not establish redistribution rights.

Qloo TLS uses `ssl.create_default_context()` with certificate verification enabled. Shopping is outside this change.

## Confirmed fashion connections

“Use as fashion inspiration” opens a small picker of the customer's private reference images. Choosing at least one image and confirming saves its IDs in the same durable local event as the fashion choice; the deck then advances without waiting for the database. Cancel leaves the card unchanged. Background batches preserve these selections across reloads and undo restores the previous connection.

The API validates image ownership and rejects missing or foreign image selections. Analytics excludes deleted images from connections and shows colors/patterns only from currently matching analysis of the selected references. Existing fashion saves can use “Connect looks” in Your direction; confirmed selections can be edited there. These edits await confirmation from the server. No shopping is added.

Migration `0009_fashion_references` adds the reference IDs to cultural feedback. All backend HTTP clients now use the operating system trust store with TLS certificate verification enabled, fixing local Windows authentication, upload, and analysis connectivity.

### My fashion direction board

Analytics → Your direction now pairs each cultural artwork with its selected private reference images. Per-card colors and patterns come only from current analysis of those references. Unlinked saves offer “Choose looks”; existing links offer “Edit connection”. “Remove connection” clears the fashion save and image links while preserving the cultural preference and the reference library. Failed mutations retain the card and show an error. Saved discoveries are shown eight at a time with a local Show more control. No shopping is added.

Validation covers ownership, actual exposures, duplicate requests, undo, offsets, exhaustion, preserved results, deduplicated visual counts, stale references, and frontend save-before-advance behavior. Headless desktop/mobile checks use sample data.
