# Topic Generation System Audit — Uniqueness via Redis

**Authority:** `docs/KLIPORA_SYSTEM_BRAIN.md` (topic memory: Redis key `used_topics` SET).  
**Scope:** GrowthAgent, WF-GEN workflow, topic_dataset.json usage, WorkflowController.start_generation_job().  
**No code was modified.**

---

## 1. Topic origins

| Source | Where it appears | Used as |
|--------|------------------|--------|
| **Telegram user input** | Telegram bot: custom prompt (`topic_mode=custom`, `custom_prompt`) or popular topic label (`topic_mode=popular`, `topic`). Sent in `/commands/generate-video` as `topic`. | WF-GEN receives as `body.topic` → `topicFromRequest`. |
| **Dashboard / API** | `POST /commands/generate-video` with `req.topic`. | Same: `body.topic` → `topicFromRequest`. |
| **trend:topics:<date>** | GrowthAgent._load_trend_topics() reads `redis.get_json("trend:topics:" + today)`. | GrowthAgent.select_topics() uses these first; only topics not in `used_topics` are returned; then passed to start_generation_job(topic=...). So they reach WF-GEN as `body.topic` (topicFromRequest). |
| **Seed list (genre topics)** | WF-GEN node “Select Unique Topic”: inline `topicData` (Mystery, Horror, Space, …) in the node’s jsCode. | Used only when **no** `topicFromRequest`; filtered by `used_topics` and one topic picked at random. |
| **topic_dataset.json** | Repo file `Datasets/topic_dataset.json` (genres + topics). | **Not used by any runtime component.** WF-GEN does not load this file; it uses an inline copy of topics in the workflow. Seed usage is effectively “inline topicData in WF-GEN”, not the JSON file. |

**Verdict (1):** Topics do originate from Telegram, dashboard, trend:topics:<date>, and from the workflow’s inline seed list. The repo’s `topic_dataset.json` is **not** used at runtime; the workflow has its own embedded seed data.

---

## 2. Check Redis before accepting a topic (SMEMBERS used_topics)

| Component | Behavior |
|-----------|----------|
| **WF-GEN** | “Get Used Topics” node: GET request to Upstash `/smembers/used_topics`. Returns `{ "result": ["...", ...] }`. “Select Unique Topic” uses `usedResult = $('Get Used Topics').item.json.result` and `usedTopics = Array.isArray(usedResult) ? usedResult : []`. So **SMEMBERS is called** and used. |
| **WF-GEN — request path** | When `topicFromRequest` is set (Telegram/dashboard/GrowthAgent), “Select Unique Topic” returns immediately with `selectedTopic: params.topicFromRequest` **without checking** `usedTopics`. So **no uniqueness check for request-provided topics.** |
| **WF-GEN — seed path** | When there is no `topicFromRequest`, topics are taken from inline `topicData`, filtered with `genreTopics.filter(t => !usedTopics.includes(t))`, and one is chosen. So **seed topics are checked** against `used_topics`. |
| **GrowthAgent** | For each candidate from trend or get_best_topics(), calls `brain.was_topic_used_recently(topic)` which uses `redis.sismember("used_topics", topic)`. So **GrowthAgent only returns topics not in used_topics.** |

**Verdict (2):** Redis `used_topics` is read via SMEMBERS in WF-GEN and used to filter **seed** topics. **Request-provided topics (Telegram, dashboard, GrowthAgent) are not checked against used_topics inside WF-GEN.** GrowthAgent does check before selecting topics for the run-cycle.

---

## 3. If topic already in used_topics → select a different one

| Path | Behavior |
|------|----------|
| **Seed path (WF-GEN)** | `available = genreTopics.filter(t => !usedTopics.includes(t))`; if genre exhausted, falls back to all genres; if all exhausted, resets to genre list. So a **new** topic is always chosen from the unused set. Correct. |
| **Request path (WF-GEN)** | Topic from request is used as-is; **no** check against `used_topics`. So the same topic can be accepted again. |
| **GrowthAgent** | Only adds to `selected` topics that satisfy `not self.brain.was_topic_used_recently(topic)`, so it never passes an already-used topic. But once that topic is used in a job, nothing adds it to `used_topics` on the request path (see below). |

**Verdict (3):** For **seed** topics, “if in used_topics then pick another” is enforced. For **request-provided** topics (Telegram, dashboard, or GrowthAgent), it is **not** enforced in WF-GEN, so repeats are possible.

---

## 4. When a topic is accepted, add to Redis (SADD used_topics)

| Where topic is accepted | SADD used_topics? |
|-------------------------|-------------------|
| **WF-GEN — seed path** | Yes. “Mark Topic Used” node: POST to Upstash `/sadd/used_topics/{{ encodeURIComponent($json.selectedTopic) }}`. Runs only when topic was **not** from request (branch “IF Topic Provided” = false → “Mark Topic Used” → “Generate Script”). So **seed-selected topics are added.** |
| **WF-GEN — request path** | No. When `topicFromRequest` is set, the flow goes straight to “Generate Script” and **skips** “Mark Topic Used”. So **Telegram/dashboard/GrowthAgent topics are never SADD’d in WF-GEN.** |
| **Mission Control** | `POST /commands/discard-job`: when user discards a preview, `r.sadd("used_topics", topic)` is called. So **discarded** jobs have their topic marked used. **Approve** does not add the topic to `used_topics`. |
| **CompanyBrain.record_success** | Calls `record_topic_used(topic)` (SADD). Used when recording a successful outcome; not invoked by WF-GEN or by the approve endpoint in the audit. |

**Verdict (4):** Seed path: SADD is applied in WF-GEN. Request path: SADD is **not** applied in WF-GEN; the only backend SADD for request topics is on **discard**, not on accept/approve. So **accepted/approved request-provided topics are never added to used_topics**, and can be reused.

---

## 5. Topic passed to WorkflowController.start_generation_job()

| Caller | Topic value | Confirmed |
|--------|-------------|-----------|
| **Dashboard** | `POST /commands/generate-video` → `ctrl.start_generation_job(topic=req.topic, ...)`. | Yes. |
| **Telegram** | Builds `body.topic` from topic_settings (custom_prompt or popular topic label or genre short); `_api_post("/commands/generate-video", body)`. | Yes. |
| **OperationsAgent** | `topics = growth_agent.select_topics(remaining_capacity)` then `for topic in topics: controller.start_generation_job(topic=topic)`. | Yes. |

**Verdict (5):** Topic is correctly passed into `start_generation_job()` from dashboard, Telegram, and OperationsAgent. WorkflowController creates the job and calls the WF-GEN webhook with `topic` in the payload; WF-GEN reads it as `body.topic` → `topicFromRequest`.

---

## 6. Summary: is topic uniqueness correctly enforced?

| Requirement | Seed topics (WF-GEN inline) | Request topics (Telegram / dashboard / GrowthAgent) |
|-------------|-----------------------------|----------------------------------------------------|
| Topics from allowed origins | Yes (inline seed + trend + Telegram/dashboard). | Yes. |
| Check Redis SMEMBERS used_topics before accept | Yes (filter in “Select Unique Topic”). | **No** — request topic is used as-is. |
| If in used_topics, select another | Yes (filter + fallback). | N/A (no check). |
| SADD used_topics when accepted | Yes (“Mark Topic Used” node). | **No** — SADD only on discard, not on accept/approve. |
| Topic to start_generation_job() | N/A (WF-GEN picks after webhook). | Yes. |

**Overall:** Uniqueness is **correctly enforced only for the seed path** (no request topic): WF-GEN loads used_topics, filters, picks an unused topic, and marks it used. For **request-provided topics** (Telegram, dashboard, or GrowthAgent), the system **does not**:

1. Check that the topic is not already in `used_topics` before accepting it in WF-GEN.  
2. Add the topic to `used_topics` when it is accepted (only when the user **discards** the video).

So the same user- or GrowthAgent-chosen topic can be used repeatedly, and GrowthAgent could theoretically reselect the same trend topic in a later cycle because it was never SADD’d.

---

## 7. Additional notes

- **topic_dataset.json:** The repo file is not loaded by WF-GEN. The workflow embeds its own topic list in the “Select Unique Topic” node. Keeping the file in sync with the workflow would require either loading the file in n8n or documenting that the source of truth for “seed” topics is the workflow JSON.
- **Regenerate:** `POST /commands/regenerate-job` calls `start_generation_job(topic=topic)` with the same job topic; WF-GEN receives it as `topicFromRequest` and does not SADD. Regenerating the same topic does not mark it used; that is consistent with “same topic, new script/visuals.”
- **Redis key:** All components use the key `used_topics` (no prefix in default project; Project 2 uses prefix `p2:` so effectively `p2:used_topics`). CompanyBrain, WF-GEN (hardcoded URL), and dashboard_api use the same semantic.

---

## 8. Conclusion

Topic uniqueness is **partially** enforced:

- **Seed path (no topic in request):** Correct: SMEMBERS used, filter applied, SADD on accept.
- **Request path (Telegram, dashboard, GrowthAgent):** Not enforced: no check against `used_topics` in WF-GEN, and no SADD on accept (only on discard). To enforce non-repeating topics for these origins, either:
  - have WF-GEN check and/or SADD when `topicFromRequest` is set, or
  - have Mission Control (or the caller) check `used_topics` before calling `start_generation_job` and SADD the topic when the job is created or when the video is approved.

No code was modified in this audit.

---

## Post-refactor (Topic Uniqueness Gate in WF-GEN)

After the refactor described in the repo:

- **Unified gate:** All topics (request and seed) pass through the same Redis check. WF-GEN runs SMEMBERS `used_topics` then the **Topic Uniqueness Gate** node: request topics already in `used_topics` are rejected unless `force_reuse` is set; seed topics are chosen only from the unused set.
- **SADD for all:** Every accepted topic is written with SADD `used_topics` (Mark Topic Used) before script generation, regardless of origin.
- **Reject path:** When a request topic is rejected, the workflow returns HTTP 400 with `{ accepted: false, reason: "topic_already_used", message: "…" }` and sends a Telegram message asking the user to re-send with `force_reuse=true` to use the topic anyway.
- **Webhook:** Supports optional `force_reuse` in the request body. Workflow responds via Respond to Webhook nodes (reject 400, success 200 with `accepted`, `job_id`, `topic`).
