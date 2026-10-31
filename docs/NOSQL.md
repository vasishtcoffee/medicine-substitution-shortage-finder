# MongoDB (rubric 4 and 9)

MongoDB stores a **non-authoritative** copy of inventory state and a **semi-structured event log**. MySQL stays the source of truth: quantities change only through MySQL and arrive in MongoDB through the outbox.

## 1. Collections (`MONGO_DATABASE`, default `medsub_feed`)

Created by the idempotent `python scripts/init_mongo.py` (`app/mongo.py: ensure_collections`: `create_collection` with a `$jsonSchema` validator, or `collMod` if it exists, then `create_index`, which is a no-op when the index exists).

### `inventory_feed` — one document per pharmacy and medicine

`_id = "ph{pharmacy_id}:med{medicine_id}"`

| Field | Type | Written by |
|---|---|---|
| `pharmacy_id`, `medicine_id` | int | sync |
| `quantity`, `reorder_level` | int ≥ 0 | sync (**never by the API**) |
| `availability` | `In stock` \| `Low` \| `Out` | sync |
| `low_stock` | bool | sync |
| `last_updated` | date | sync |
| `source` | string (`sale`, `receipt`, `adjustment`, `resync`) | sync |
| `metadata` | object, free-form (e.g. `last_batch_no`, `last_expiry_date`, supplier hints) | sync (batch/expiry) and admin |
| `notes` | string | admin |
| `flags` | array of strings | admin |

Indexes: `ix_feed_pharmacy`, `ix_feed_medicine`, `ix_feed_last_updated`.

### `feed_events` — append-only events from different sources

`_id = "<source>:<movement_id>"` for synced events (stable, so re-applying is idempotent) or `manual:<uuid>` for admin-created ones.

| Field | Type |
|---|---|
| `source` | `sale` \| `receipt` \| `adjustment` \| `import` |
| `pharmacy_id`, `medicine_id` | int (optional) |
| `occurred_at` | date |
| `payload` | object — **shape varies by source** (sale: `delta`, `order_id`, `quantity_after`; receipt: `batch_no`, `expiry_date`; import: arbitrary supplier JSON) |
| `notes`, `flags` | string, array |

This variable `payload` is the semi-structured justification for a document store. Indexes: `ix_events_source`, `ix_events_occurred`, `ix_events_ph_med`.

## 2. CRUD (admin only; API + Feed Lab screen)

| Operation | API | Rules |
|---|---|---|
| **Create** | outbox sync (upsert) · `POST /feed/events` | Manual events are stored unverified (`flags: ["manual","unverified"]`) and never change MySQL. |
| **Read** | `GET /feed/inventory`, `GET /feed/events` (+ `/{id}`) | Filters: pharmacy, medicine, source, date range; `page`/`page_size`. |
| **Update** | `PATCH /feed/inventory/{id}`, `PATCH /feed/events/{id}` | Only `metadata`, `notes`, `flags` (pydantic `extra="forbid"` → 422 for anything else, e.g. `quantity`). Later syncs do not wipe admin notes/flags. |
| **Delete** | `DELETE /feed/inventory/{id}`, `DELETE /feed/events/{id}` | Never touches MySQL. `POST /sync/resync` recreates a deleted feed document. |

## 3. Outbox sync (eventual consistency)

* Every stock change (`sp_receive_stock`, `sp_adjust_stock`, `sp_set_reorder_level`, `sp_complete_order`) writes `sync_outbox` rows **in the same MySQL transaction** via `sp_write_outbox`.
* Contract (payload JSON):
  * `UPSERT_INVENTORY_FEED`, `entity_id = ph{p}:med{m}`: `{pharmacy_id, medicine_id, quantity, reorder_level, availability, low_stock, source, occurred_at, metadata:{last_batch_no, last_expiry_date}}`
  * `APPEND_FEED_EVENT`, `entity_id = {source}:{movement_id}`: `{source, pharmacy_id, medicine_id, delta, order_id, quantity_after, occurred_at, details:{batch_no, expiry_date}}`
* Worker (`app/sync.py`): background task every `SYNC_INTERVAL_SECONDS`, after every stock-changing request, and `POST /sync/run`. Rows are processed in `id` order. Upserts are keyed by `_id` and guarded by `last_updated <= occurred_at`, so replays and out-of-order retries are harmless; event inserts use `$setOnInsert`.
* Status: `PENDING` → `DONE`, or `FAILED` with `attempts+1` and `last_error`. Retries stop at `SYNC_MAX_ATTEMPTS` (5); `POST /sync/retry-failed` resets them.
* **Failure handling:** if MongoDB is down the sale is already committed in MySQL; the worker records the error, stops hammering the server (it breaks out after the first connection failure) and rows stay `PENDING`/`FAILED`. When MongoDB returns, a normal run drains them. If documents were lost or deleted, `POST /sync/resync` (`sp_enqueue_full_resync`) re-enqueues every inventory row.
* Viva note: this is **eventual consistency** — MongoDB can lag MySQL, never the reverse.

## 4. Status of verification

Tests in `tests/nosql/test_feed_and_sync.py` run on **mongomock** by default and passed (14/14, incl. the `$jsonSchema` validator and `init_mongo.py` idempotency tests) against a **real MongoDB 7.0.14** (portable zip run locally). The real run found and fixed an unstable-pagination bug. To repeat:

```powershell
docker compose up -d mongo
$env:MONGO_TEST_URI = "mongodb://127.0.0.1:27017"
python -m pytest tests/nosql -q
python scripts/init_mongo.py
```
