# Research Report (2026-11-14)

Legend: [V] verified against a primary source fetched today; [S] secondary/vendor source only; [U] unverified.

## 1. Dodo Payments vs dodo_client.py / billing_service.py

### Confirmed correct [V]
- Headers `webhook-id`, `webhook-signature`, `webhook-timestamp`; signed content `{id}.{timestamp}.{raw body}`; secret `whsec_` prefix then base64-decode; HMAC-SHA256 then base64; header holds space-separated `v1,<sig>` values; 5 minute tolerance. https://docs.dodopayments.com/developer-resources/webhooks
- Base URLs `https://test.dodopayments.com` and `https://live.dodopayments.com`; `Authorization: Bearer`; keys `dodo_test_...` / `dodo_live_...` only work on their own mode's URL. https://docs.dodopayments.com/api-reference/introduction
- `POST /subscriptions` takes `product_id`, `quantity`, `customer` (`email` required for new), `billing` (only `country` required), optional `payment_link`, `return_url`, `metadata`. Response has `subscription_id`, `payment_link`, `customer.customer_id`. https://docs.dodopayments.com/api-reference/subscriptions/post-subscriptions
- Event names `subscription.active`, `.renewed`, `.on_hold`, `.failed`, `.cancelled`, `.expired` all exist. https://docs.dodopayments.com/developer-resources/webhooks/intents/subscription

### Mismatches / risks
1. **Deprecated endpoint.** `POST /subscriptions` is marked deprecated; docs recommend Checkout Sessions `POST /checkouts` for new integrations. [V] https://docs.dodopayments.com/api-reference/subscriptions/post-subscriptions . Checkout Sessions: only `product_cart` (`[{product_id, quantity}]`) required; `customer`, `billing_address`, `return_url`, `metadata` optional; response `session_id` and `checkout_url` (nullable). [V] https://docs.dodopayments.com/api-reference/checkout-sessions/create . Action: switch to `/checkouts`; billing_service already falls back to `checkout_url`, but `payload` field names change (`product_cart`, `billing_address`), so update HttpxDodoClient.
2. **Hardcoded `billing: {"country": "US"}`** is schema-valid but wrong for non-US buyers (may affect tax). With `/checkouts`, billing_address is optional, so omit it and let the hosted page collect it.
3. **Missing event: `subscription.past_due`** (named on the webhooks page) is not in EVENT_STATUS. Also unhandled: `subscription.paused`, `.unpaused`, `.updated`, `.plan_changed`, `.update_payment_method`. [V] Add at least past_due -> past_due, paused, plan_changed (to update plan). `.updated`/`.plan_changed` should be handled or intentionally ignored.
4. **`subscription.failed` -> past_due is a guess.** Docs list the event but the fetched page gave no semantics. [U] Check Event Payloads docs before mapping (it may mean subscription creation failed, not a renewal failure).
5. **Payload shape unverified.** Docs confirm `subscription_id`, `status`, `next_billing_date`, `metadata` on subscription events, and top-level `business_id`, `type`, `timestamp`, `data` with `data.payload_type`. [V] The fetched pages did not document `data.customer.customer_id`. [U] Also unverified: whether checkout-session `metadata` propagates onto the subscription webhook (the user_id fallback path depends on it). Test in test mode with a real webhook and log the payload before launch. Consider using `status` from the payload as the source of truth instead of only the event name.
6. Quantity: schema says min 0 but description says at least 1; code sends 1 (fine).
7. Webhook secret: code accepts raw (non-whsec_) secrets as plain bytes. Docs only describe the `whsec_` form; harmless but could hide misconfiguration. Optional: fail closed.

## 2. Amazon data source recommendation

| Source | Provides | Cost/limits | ToS |
|---|---|---|---|
| Keepa API | Sales rank history, price history, offers; `monthlySold` is Amazon's "bought in past month" bucket where available [S] | Entry EUR 49/mo for 20 tokens/min, up to EUR 11,099 for 10,000/min; tokens expire after 60 min [S] https://revenuegeeks.com/software/keepa/pricing ; 1 token per ASIN product request [S] https://www.nexscope.ai/blog/keepa-api-guide . Keepa's own pricing/doc pages did not render for me: [U] | Licensed data API; no scraping by you |
| Rainforest API (Traject Data) | Product details, reviews, search, BSR/category data, pricing, sellers [V] | $23/mo (500 credits) to $83/mo (10k) to $375/mo (250k); overage $0.003-$0.06/credit; annual-billing prices [V] https://trajectdata.com/pricing/rainforest-api | It scrapes Amazon on your behalf; Amazon's Conditions of Use page was unreachable (503) [U]; scraping risk sits with the vendor but is a business-continuity risk |
| Amazon SP-API | Catalog Items `salesRanks` (v2020-12-01, 2 rps burst 2) and Product Fees estimates (batch up to 20) [V] https://developer-docs.amazon.com/sp-api/docs/catalog-items-api-v2020-12-01-reference https://developer-docs.amazon.com/sp-api/docs/product-fees-api | Free, but needs a seller/developer registration and per-seller authorization; no sales estimates, no review text, no history; Acceptable Use Policy fetch redirected and I could not read it [U] | Official, but intended for sellers' own data/catalog; third-party market research use must be checked against the AUP [U] |

Recommendation: implement **Keepa** first behind ProductDataProvider (`get_product`, `get_bsr_history` map directly to its product/sales-rank history; monthly sales from `monthlySold`, else a BSR-to-sales curve estimate labelled as an estimate). Reasons: licensed data, history included, cheapest meaningful entry. Weakness: no review text, so `get_reviews` needs Rainforest (reviews are in its data types [V]) or return empty. Use SP-API Product Fees later for the fee calculator. Avoid direct scraping. Keepa `monthlySold` and token costs should be verified in Keepa's own docs before budgeting [U].

## 3. FBA fees

- US referral fees [V, sell.amazon.com/pricing, copyright 2026, no effective date shown]: most categories 15% (Home & Kitchen, Toys, Tools, Pet, Everything Else); Computers/Consumer Electronics/Video Game Consoles 8%; Grocery 8% up to $15 then 15%; Clothing 5%/10%/17% by price tier; Jewelry 20% up to $250, 5% above; Watches 16%/3% at $1,500; Media 15% plus $1.80 closing fee; most categories $0.30 minimum. https://sell.amazon.com/pricing
- So the "Use 15% of price" helper is a reasonable default but wrong for electronics (8%), clothing, jewelry, grocery. Recommend: label it "typical" and add an optional category dropdown or a note that the $0.30 minimum applies.
- FBA fulfillment fees are weight/size-tier based and not exposed as a flat percentage; Amazon's FBA pricing page returned 404 [U]. Fulfillment fee should stay a manual input (or come from SP-API Product Fees later).
- Storage: vendor blogs give standard-size roughly $0.78/cu ft Jan-Sep and $2.40/cu ft Oct-Dec, with some claiming a mid-2026 increase to $0.87 and new aged-inventory surcharges; sources conflict [S]. https://www.novadata.io/resources/blog/amazon-fba-storage-fees . Storage fee is per cubic foot per month, so a single per-unit `storage_fee` field is fine as a manual input. A reported 3.5% fuel/logistics surcharge from April 2026 appears in one source only [U].
- Fees change annually; add a "verify in Seller Central" note and the date on the calculator. `vat_tax` as a user-entered field is reasonable.

## 4. Dependency advisories

Backend (requirements.txt, all `>=` with no upper pins or lockfile):
- **python-jose**: latest on PyPI is 3.5.0 (2025-05-28) [V, pypi.org JSON]. Historical CVE-2024-33663 (ECDSA algorithm confusion) and CVE-2024-33664 (JWE decompression DoS) affected <=3.3.0 [S] https://security.snyk.io/package/pip/python-jose ; FastAPI community has moved away from it [S] https://github.com/tiangolo/fastapi/discussions/11345 . Several aggregator claims (CVE-2025-61152 alg=none, CVE-2026-85394) I could not verify [U]. Recommendation: replace with **PyJWT** (2.15.1, 2026-09-28 [V]) since only HS256 access tokens are needed; at minimum pin `python-jose>=3.5.0` and explicit `algorithms=["HS256"]`.
- **slowapi** 0.1.10 released 2026-06-13 [V, PyPI]; maintained enough. Advisory search returned nothing [U]. Note it uses in-memory storage by default (per-process), so use Redis for multi-worker deploys.
- authlib 1.9.5 (2026-11-05), fastapi 0.162.7, bcrypt 5.0.0 are current [V]; with `>=` a fresh install gets them. No advisory check performed on these [U]. Recommend pinning with a lock file (pip-compile/uv) and running `pip-audit` in CI.
- `python-multipart`, `psycopg2-binary` loose pins: have had past advisories; run pip-audit [U].

Frontend (package.json):
- `npm audit` in frontend/ reports 0 vulnerabilities (275 deps) [V, run locally today].
- All versions in package.json equal the current npm latest (axios 1.21.1, react-router-dom 7.18.5, vite 8.3.x, typescript 7.0.2, vitest 5.1.0, etc.) [V, npm view]. No deprecated packages identified, but I did not run `npm view <pkg> deprecated` for transitive deps [U].
- Caret ranges are fine since package-lock presumably exists; commit it.
