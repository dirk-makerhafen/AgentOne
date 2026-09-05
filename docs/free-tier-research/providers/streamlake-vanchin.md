---
name: StreamLake Vanchin (快手万擎)
url: "https://www.streamlake.com/product/wanqing"
setup_instructions: |
  1. Register at https://www.streamlake.com, complete real-name verification (实名认证), and activate (开通) the 快手万擎 service console.
  2. Create an API key in the console under 系统管理与统计 → API Key 管理 (https://console.streamlake.com/console/wanqing/api-key). Store it as WQ_API_KEY; the generated key has full access to all resources under the project.
  3. Under 模型服务 → 在线推理, create a 推理服务 (inference endpoint) for your chosen model (or use a prebuilt KAT-series endpoint) and copy its endpoint ID (ep-xxx), which is passed as the `model` parameter.
  4. Claim any free resource packs (费用中心 → 资源包管理, or the activity page) and call https://wanqing.streamlakeapi.com/api/gateway/v1/endpoints (chat path /api/gateway/v1/endpoints/chat/completions) with header `Authorization: Bearer YOUR_API_KEY` using any OpenAI-compatible client.
api_key_url: "https://console.streamlake.com/console/wanqing/api-key"
limits: {}
---

ONE-TIME new-user grant (not a permanent tier; re-verified 2026-09-05): StreamLake (Beijing Xiliu Lake Technology, Kuaishou) documents free inference resource packs for new, real-name-verified 快手万擎 users, granted in batches; exact current amounts are only stated per the linked activity page.

**Free Tier:**

- One-time new-user free inference resource packs ("免费推理资源包"/"免费推理试用额度"), confirmed by three current official doc pages (product intro, quickstart updated 2025-12-30, free-quota page updated 2025-12-12). Granted in batches after registration + service activation; check 费用中心 → 资源包管理 for balance.
- Covers online-inference input, output, and cache-hit tokens only; cannot抵扣 batch inference. Quotas are per base model and shared under the master account (a fine-tuned model shares its base model's quota).
- No payment required to register or to receive the new-user packs. Overrun warning: when free quota is exhausted, continued use is billed postpaid by token usage, and insufficient balance freezes service — monitor quota (SMS reminders documented).

**Free Models:**

- No static free model IDs: the `model` parameter is your per-user endpoint ID (e.g. `ep-xxx-xxx`), created per model; KAT-series models offer prebuilt endpoints.
- Eligible base models are "基础模型" per the free-quota doc, exact per-model applicability "以资源包领取页面说明为准" (unknown without login). Representative roster from the live product/pricing page (fetched 2026-09-05, verify live): `DeepSeek-V4-Flash-0731`, `DeepSeek-V4-Flash`, `DeepSeek-V4-Pro-0813`, `DeepSeek-V4-Pro`, `GLM-5.3`, `GLM-5.2`, `GLM-5.1`, `GLM-5-Turbo`, `MiniMax-M2.7`, `MiniMax-M2.5`, `MiniMax-M2.1-lightning`, `Kimi-K2.6`, `Kimi-K2.5`, `MiMo-V2.5-Pro`, `Qwen3.6-27B`, `Qwen3.5-35B-A3B` / `Qwen3.5-27B` / `Qwen3.5-122B-A10B` / `Qwen3.5-397B-A17B`, `KAT-Coder-Pro-V2.5`, `KAT-Coder-Air-V2.5`, `KAT-Coder-Pro-V2` (context lengths: unknown).
- No `models/` card links: the provider-side ID is always the per-user endpoint ID (not the base-model name), and free eligibility per base model is login-gated, so no 1:1 mapping to catalog cards (e.g. `deepseek-v4-flash`, `deepseek-v4-pro`, `minimax-m3`) can be asserted.

**Limits:**

- No current exact quota figures are publicly documented: the free-quota page defers amounts to an activity说明 doc link that returns 404 (checked 2026-09-05), and the last dated campaign (see Notes) expired 2025-11-16.
- Per-model and per-endpoint throttles are user-configurable caps, not free-tier allowances — unknown defaults.

**Notes:**

- Account required; API key required (Bearer); real-name verification required (实名认证, documented as a participation condition). CN phone requirement: unknown.
- Expired reference (not current): the "快手万擎千万Tokens免费体验" campaign ran 2025-09-28–2025-11-16 with 初识礼包 150万 tokens (activate console), 探索礼包 300万 tokens (first successful API call), 首金礼包 600万 tokens (first recharge ≥100元 — payment-gated), 万金礼包 5000万 tokens (cumulative spend ≥10000元 — payment-gated); all packs 180-day validity, manually claimed. Do not treat these figures as current.
- Deduction uses per-model input/output/cache coefficients (input price = coefficient 1), so pack-token burn exceeds raw token counts on output-heavy calls.
- Operator: 北京溪流湖科技有限公司 (Beijing Xiliu Lake Technology); 京ICP备19034532号-192.

**Sources**

- https://www.streamlake.com/document/WANQING/mdsor5767ob7s796sp6
- https://www.streamlake.com/document/WANQING/mdptab9x4xn2v4vyo9v
- https://www.streamlake.com/document/WANQING/mdpta4y9jeqsxdgqldl
- https://www.streamlake.com/activity/vanchin
- https://www.streamlake.com/document/WANQING/me6yi4shauyxx5fhdtv
- https://www.streamlake.com/document/WANQING/mdsotohqdfg0wpfn4u9
- https://www.streamlake.com/product/wanqing
