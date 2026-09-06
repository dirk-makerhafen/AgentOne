---
name: iFlytek Spark (讯飞星火)
url: "https://xinghuo.xfyun.cn/sparkapi"
setup_instructions: |
  1. Register at https://www.xfyun.cn (phone login; +86 default, international codes accepted on the form) and create an app in the console (https://console.xfyun.cn/app/myapp); complete personal or enterprise real-name verification.
  2. Claim the free pack for 星火认知大模型 on the product/price page (https://xinghuo.xfyun.cn/sparkapi?scr=price) or via the console free-claim link (one claim per product per identity).
  3. In the console (https://console.xfyun.cn/services/bmx1), copy the per-model-version APIPassword for the version you will call.
  4. Call https://spark-api-open.xf-yun.com/v1/chat/completions with header `Authorization: Bearer <APIPassword>` using any OpenAI-compatible client (`base_url` https://spark-api-open.xf-yun.com/v1/), with a version ID as `model`.
api_key_url: "https://console.xfyun.cn/services/bmx1"
limits:
  requests:
    second: 2
---

ONE-TIME free packs (not a permanent tier), plus a documented free Lite version: iFlytek's SparkDesk/星火 offers new real-name-verified users a one-time token free pack (personal 2M tokens / enterprise 5M tokens, 1-year validity, QPS 2), while Spark Lite is documented as free to use ("支持免费使用"). Re-verified 2026-09-05.

**Free Tier:**

- One-time free pack for 星火认知大模型V3.0: personal 2M tokens, QPS 2, 1-year validity, ¥0; enterprise 5M tokens, QPS 2, 1-year validity, ¥0 (official pricing page, console 免费领取 links; re-verified 2026-09-05). One claim per product per identity (personal vs enterprise fixed at claim time).
- Spark Lite: official HTTP doc lists Lite as "轻量级大语言模型…支持免费使用" — the only version explicitly documented free; no Lite price is listed (re-verified 2026-09-05).
- New-user free packs require real-name verification (personal or enterprise); no payment/billing step documented for claiming the free pack.

**Free Models:**

- `lite` — 8K max input, 4K max output (documented free use).
- `generalv3` (Pro) — 8K max input, 8K max output.
- `pro-128k` (Pro-128K) — 128K max input, 4K max output (official version table, re-verified 2026-09-05; max_tokens range [1,32768], default 4096).
- `generalv3.5` (Max) — 8K max input, 8K max output.
- `max-32k` (Max-32K) — 32K max input, 8K max output.
- `4.0Ultra` (Ultra) — 32K max input, 32K max output (max_tokens range [1,32768], default 32768).
- Versions meter tokens independently ("各版本独立计量tokens"); which versions the one-time free pack meters against is undocumented — verify in console.
- No overlap with the model catalog: iFlytek serves only its own Spark version IDs, so none of the `models/` cards applies here.

**Limits:**

- Free pack: QPS 2, recorded as 2 requests/second in frontmatter (official pricing page; no per-minute, per-day, or token-rate figures beyond the pack totals).
- WebSocket error codes document daily (11201), per-second (11202), and concurrency (11203) throttles, but no numeric values are published.
- 1 token ≈ 1.5 Chinese characters or 0.8 English words (documented conversion).
- Third-party trackers report 5 RPM on the trial path — unverified against official docs, do not use.

**Notes:**

- Account required; key required — HTTP/OpenAI-compatible calls use per-version APIPassword (Bearer); legacy WebSocket calls use AppID + APIKey + APISecret (not OpenAI-compatible).
- Phone verification: registration is phone-based (defaults to +86; console forms accept international codes) — whether a CN number is strictly required is unknown. Real-name verification required for the free pack. No payment info required to claim it.
- Max deprecation: Max-version packages go offline 2026-03-10; backend service merges into Ultra with combined authorization usage (official HTTP doc notice, re-verified 2026-09-05).
- 10007 flow-control: one outstanding request per connection (must wait for full reply before sending the next).
- Operator: 科大讯飞股份有限公司 (iFLYTEK); 皖ICP备05001217号-71.
- Data usage/training policy: unknown.

**Sources**

- https://www.xfyun.cn/doc/spark/HTTP%E8%B0%83%E7%94%A8%E6%96%87%E6%A1%A3.html (HTTP doc: Lite free statement, endpoint, model IDs, context lengths, APIPassword auth, error codes)
- https://www.xfyun.cn/activities/discount (official pricing page: personal 2M / enterprise 5M free packs, QPS 2, 1-year validity)
- https://www.xfyun.cn/free (new-user free-package program: real-name requirement, one-claim rule)
- https://www.xfyun.cn/doc/spark/Web.html (WebSocket doc: domain IDs lite/generalv3/pro-128k/generalv3.5/max-32k/4.0Ultra, endpoints)
- https://www.xfyun.cn/doc/spark/Guide.html (FAQ: personal users have free quota)
