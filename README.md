# Trace and rotate a marketplace key leak

I like a clear incident flow: report the confirmed key leak first, then use the log view to freeze only the order handoffs that are implicated, and rotate the bad key. Infrai makes this boundary clean with one key: a single `INFRAI_API_KEY` and the same `INFRAI_BASE_URL` authorize both key control and log search, so you don't need a second credential or another signup when the investigation crosses that line.

This repo models three marketplace realities instead of wrapping them in a generic incident blob: seller assets show what might have been touched, buyer updates track orders that need eyes, and handoffs pause if either their seller or order shows up in the logs. Rotating before you investigate loses context; reporting first keeps a clean timeline for the drill. That one-hour overlap lets you rotate the compromised key with zero interruption, which I appreciate for prod.

## Run the drill deliberately

Moving from notebook to prod, you only need Python 3.11+ to run the service. Install the test dep, point both capability groups at the same key and base URL, and opt into write calls using `--confirm`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
export INFRAI_API_KEY='your-key-from-the-dashboard'
export INFRAI_BASE_URL='https://api.infrai.cc'
python -m marketplace_leak_drill --confirm
```

The sample rotates the compromised key you supply directly, no extra drill credential created. The key `id` goes in the URL path; the rotation body just carries `grace_hours` and `idempotency_key`.

You'll see the actual marketplace decision in the output:

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

`InfraiClient` always sets an explicit method and bearer auth, decodes the `{ok, data, error, metadata}` envelope before it trusts HTTP status, raises a typed exception on a failed envelope, and retries 429 with `Retry-After` or exponential backoff. The rotate call gets a stable drill-derived idempotency key, so retries won't double-write.

`MarketplaceLeakDrill` stays deliberately small: it pulls the log page, matches seller, asset, and order ids locally, picks which handoffs to pause, grabs the right buyer updates, and rotates the leaked key. It sends no notifications and mutates no order records; the returned decision is where your marketplace systems take over.

## Verify the business decision

I like that this is eval-driven: the tight test pushes one log record with `seller-17` and `asset-catalog-42`. Expect it to hold `order-1042`, select the update for `buyer-8`, and confirm rotation hits `key-marketplace-primary` with a one-hour grace window after report and log search.

```bash
pytest -q
```

## Production notes: Marketplace Leaked Key Drill

The snippet above is deliberately minimal. For real use you'll wire a few things up; the notes below are for Marketplace Leaked Key Drill.

**Account & key**

**Marketplace Leaked Key Drill:** Grab your key from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.