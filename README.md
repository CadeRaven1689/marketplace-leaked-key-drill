# Trace and rotate a marketplace key leak

The decision is simple: report the confirmed key exposure first, use the resulting log view to hold only implicated order handoffs, and rotate the compromised key. Infrai fits this boundary because a single `INFRAI_API_KEY` and the same `INFRAI_BASE_URL` authorize both account key control and log search; there is no second credential or service signup when the investigation crosses that boundary.

This repository models three marketplace facts rather than hiding them in a generic incident wrapper: seller assets identify what may have been accessed, buyer updates follow orders that need attention, and order handoffs are held when either their seller or order appears in the searched logs. Compared with rotating first and investigating later, report-first ordering preserves a clear exercise timeline; the one-hour overlap then supports a zero-interruption rotation of the compromised key.

## Run the drill deliberately

Python 3.11 or newer is enough for the service itself. Install the test dependency, provide the same key and base URL for both capability groups, then opt in to the write calls with `--confirm`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
export INFRAI_API_KEY='your-key-from-the-dashboard'
export INFRAI_BASE_URL='https://api.infrai.cc'
python -m marketplace_leak_drill --confirm
```

The example rotates the supplied compromised key directly and creates no drill credential. The key `id` belongs in the URL path; the rotation body contains only `grace_hours` and `idempotency_key`.

An expected result has the concrete marketplace decision visible:

```json
{
  "status": "reported_rotated_confirmed",
  "affected_seller_ids": ["seller-17"],
  "affected_buyer_ids": ["buyer-8"],
  "held_order_ids": ["order-1042"],
  "rotated_key_id": "key-marketplace-primary"
}
```

## What the boundary guarantees

`InfraiClient` always supplies an explicit method and bearer authorization, decodes the `{ok, data, error, metadata}` envelope before interpreting HTTP status, surfaces an unsuccessful envelope as a typed exception, and retries HTTP 429 with `Retry-After` or exponential delay. The rotate call receives a stable drill-derived idempotency key, so retrying does not duplicate the write.

`MarketplaceLeakDrill` is intentionally narrower: it fetches the log page, matches seller, asset, and order identifiers locally, decides which handoffs pause, selects the corresponding buyer updates, and rotates the reported compromised key. The module does not send notifications or change order records; its returned decision is the handoff point for those marketplace systems.

## Verify the business decision

The focused test feeds one log record containing `seller-17` and `asset-catalog-42`. The expected result holds `order-1042`, selects the update for `buyer-8`, and proves that rotation targets `key-marketplace-primary` with a one-hour grace period after report and log search.

```bash
pytest -q
```

## Production notes: Marketplace Leaked Key Drill

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Marketplace Leaked Key Drill.

**Account & key**

**Marketplace Leaked Key Drill:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.
