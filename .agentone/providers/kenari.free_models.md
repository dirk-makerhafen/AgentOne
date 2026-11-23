---
provider: kenari
name: Kenari
free_verified: '2026-09-05'
models:
- provider_model_id: muse-spark-1-2-contributor:free
  model: muse-spark-1.2-contributor
  conditions: '`:free` lane billed Rp 0; account + key, no card; live-catalog-verified
    2026-09-05 (all `free: true`, no sunset set); per-minute cap + daily quota tiers'
  verified: '2026-09-05'
- provider_model_id: laguna-s-2-1:free
  model: laguna-s-2.1
  conditions: '`:free` lane billed Rp 0 (live-catalog-observed 2026-09-05); account
    + key (`kn-...`), no top-up; confirm via GET /v1/models'
  verified: '2026-09-05'
- provider_model_id: agnes-2-5-flash:free
  model: agnes-2.5-flash
  conditions: :free lane billed Rp 0, best-effort; account + key (kn-...), no top-up
  verified: '2026-09-05'
- provider_model_id: step-3-7-flash:free
  model: step-3-7-flash
  conditions: :free lane billed Rp 0, best-effort; account + key (kn-...), no top-up
  verified: '2026-09-05'
- provider_model_id: muse-spark-1-3-contributor:free
  model: muse-spark-1.3-contributor
  conditions: '`:free` lane billed Rp 0; account + key, no card; live-catalog-verified
    2026-09-05 (all `free: true`, no sunset set); per-minute cap + daily quota tiers'
  verified: '2026-09-05'
- provider_model_id: nemotron-3-super-120b-a12b:free
  model: nemotron-3-super-120b-a12b
  conditions: '`:free` lane billed Rp 0 (live-catalog-observed 2026-09-05); account
    + key (`kn-...`), no top-up; confirm via GET /v1/models'
  verified: '2026-09-05'
- provider_model_id: mimo-v2-5:free
  model: mimo-v2.5
  conditions: :free lane billed Rp 0, best-effort; account + key (kn-...), no top-up
  verified: '2026-09-05'
- provider_model_id: laguna-xs-2-1:free
  model: laguna-xs-2.1
  conditions: '`:free` lane billed Rp 0 (live-catalog-observed 2026-09-05); account
    + key (`kn-...`), no top-up; confirm via GET /v1/models'
  verified: '2026-09-05'
- provider_model_id: nemotron-3-ultra-550b-a55b:free
  model: nemotron-3-ultra-550b-a55b
  conditions: '`:free` lane billed Rp 0 (live-catalog-observed 2026-09-05); account
    + key (`kn-...`), no top-up; confirm via GET /v1/models'
  verified: '2026-09-05'
- provider_model_id: hy3:free
  model: hy3
  conditions: :free lane billed Rp 0, best-effort; account + key (kn-...), no top-up
  verified: '2026-09-05'
  notes: Kenari catalogs 262K context (slightly above official 256K max; treat 256K
    as the cap)
limits:
  requests:
    minute: 5
    day: 50
---


# Free models offered by Kenari
