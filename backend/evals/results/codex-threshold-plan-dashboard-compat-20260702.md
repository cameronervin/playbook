# Eval run: dashboard_insights

- **Run name:** codex-threshold-plan-dashboard-compat-20260702
- **When:** 2026-07-02T17:31:08+00:00
- **Result:** PASS

## Metadata

- **commit_sha:** "0190230a22ab07fe5db32d066e9900a396d87bc0"
- **created_at:** "2026-07-02T17:31:08+00:00"
- **dataset:** "dashboard_insights"
- **dataset_path:** "evals/datasets/dashboard_insights.yaml"
- **environment:** "local"
- **eval_embeddings_model:** "text-embedding-3-small"
- **eval_judge_model:** "playbook-chat"
- **kb_provider_mode:** "local"
- **llm_chat_model:** "playbook-chat"
- **llm_provider_mode:** "litellm"
- **max_concurrency:** 1
- **thresholds:** {"dashboard_insights_metric_grounding": 1.0, "dashboard_insights_risk_labels": 1.0, "dashboard_insights_source_grounding": 1.0, "dashboard_insights_topic_labels": 1.0, "dashboard_insights_unanswered_coverage": 1.0}

## Mean scores

| Criterion | Mean |
| --- | --- |
| dashboard_insights_metric_grounding | 1.000 |
| dashboard_insights_risk_labels | 1.000 |
| dashboard_insights_source_grounding | 1.000 |
| dashboard_insights_topic_labels | 1.000 |
| dashboard_insights_unanswered_coverage | 1.000 |

## Per-item scores

### 4c911246d5259f53
_trace: 0399b393ff90379b5c712532b3dfcee5_

| Criterion | Score | Reasoning |
| --- | --- | --- |
| dashboard_insights_metric_grounding | 1.0 | generated counts are bounded by source counts |
| dashboard_insights_risk_labels | 1.0 | expected risk labels present |
| dashboard_insights_source_grounding | 1.0 | source message IDs are present and allowed |
| dashboard_insights_topic_labels | 1.0 | expected topic labels present |
| dashboard_insights_unanswered_coverage | 1.0 | unanswered output matches seeded unanswered data |

### 09ac7aedabf87509
_trace: 4ddae821572328897bca62ed9b354521_

| Criterion | Score | Reasoning |
| --- | --- | --- |
| dashboard_insights_metric_grounding | 1.0 | generated counts are bounded by source counts |
| dashboard_insights_risk_labels | 1.0 | expected risk labels present |
| dashboard_insights_source_grounding | 1.0 | source message IDs are present and allowed |
| dashboard_insights_topic_labels | 1.0 | expected topic labels present |
| dashboard_insights_unanswered_coverage | 1.0 | unanswered output matches seeded unanswered data |

### 9000a36155198255
_trace: a7bc5685c0460f508b2d18213caba7f4_

| Criterion | Score | Reasoning |
| --- | --- | --- |
| dashboard_insights_metric_grounding | 1.0 | generated counts are bounded by source counts |
| dashboard_insights_risk_labels | 1.0 | expected risk labels present |
| dashboard_insights_source_grounding | 1.0 | source message IDs are present and allowed |
| dashboard_insights_topic_labels | 1.0 | expected topic labels present |
| dashboard_insights_unanswered_coverage | 1.0 | unanswered output matches seeded unanswered data |

### 299c597c123fc14e
_trace: b7c5dadf37a1f7cd938e7aefaa20fbb2_

| Criterion | Score | Reasoning |
| --- | --- | --- |
| dashboard_insights_metric_grounding | 1.0 | generated counts are bounded by source counts |
| dashboard_insights_risk_labels | 1.0 | expected risk labels present |
| dashboard_insights_source_grounding | 1.0 | source message IDs are present and allowed |
| dashboard_insights_topic_labels | 1.0 | expected topic labels present |
| dashboard_insights_unanswered_coverage | 1.0 | unanswered output matches seeded unanswered data |

### d1732b45a5c7a27a
_trace: 907173c8f3c24992892f23f6bfbe9497_

| Criterion | Score | Reasoning |
| --- | --- | --- |
| dashboard_insights_metric_grounding | 1.0 | generated counts are bounded by source counts |
| dashboard_insights_risk_labels | 1.0 | expected risk labels present |
| dashboard_insights_source_grounding | 1.0 | source message IDs are present and allowed |
| dashboard_insights_topic_labels | 1.0 | expected topic labels present |
| dashboard_insights_unanswered_coverage | 1.0 | unanswered output matches seeded unanswered data |

### c2d328bf34a34690
_trace: 8a775e1abceeebb38c34e4d8244deaf3_

| Criterion | Score | Reasoning |
| --- | --- | --- |
| dashboard_insights_metric_grounding | 1.0 | generated counts are bounded by source counts |
| dashboard_insights_risk_labels | 1.0 | expected risk labels present |
| dashboard_insights_source_grounding | 1.0 | source message IDs are present and allowed |
| dashboard_insights_topic_labels | 1.0 | expected topic labels present |
| dashboard_insights_unanswered_coverage | 1.0 | unanswered output matches seeded unanswered data |

### a5526a26a3012e95
_trace: 762a6bcd070699de4b9476bfac459ad6_

| Criterion | Score | Reasoning |
| --- | --- | --- |
| dashboard_insights_metric_grounding | 1.0 | generated counts are bounded by source counts |
| dashboard_insights_risk_labels | 1.0 | expected risk labels present |
| dashboard_insights_source_grounding | 1.0 | source message IDs are present and allowed |
| dashboard_insights_topic_labels | 1.0 | expected topic labels present |
| dashboard_insights_unanswered_coverage | 1.0 | unanswered output matches seeded unanswered data |

### 52060bc3c2321c05
_trace: dc27b6ec282cf2344881879a0672146c_

| Criterion | Score | Reasoning |
| --- | --- | --- |
| dashboard_insights_metric_grounding | 1.0 | generated counts are bounded by source counts |
| dashboard_insights_risk_labels | 1.0 | expected risk labels present |
| dashboard_insights_source_grounding | 1.0 | source message IDs are present and allowed |
| dashboard_insights_topic_labels | 1.0 | expected topic labels present |
| dashboard_insights_unanswered_coverage | 1.0 | unanswered output matches seeded unanswered data |

### 011cde6098d0fa53
_trace: 8cd8b377213c6adf50778f748c8e8eed_

| Criterion | Score | Reasoning |
| --- | --- | --- |
| dashboard_insights_metric_grounding | 1.0 | generated counts are bounded by source counts |
| dashboard_insights_risk_labels | 1.0 | expected risk labels present |
| dashboard_insights_source_grounding | 1.0 | source message IDs are present and allowed |
| dashboard_insights_topic_labels | 1.0 | expected topic labels present |
| dashboard_insights_unanswered_coverage | 1.0 | unanswered output matches seeded unanswered data |

### 2223a276f0de1a4e
_trace: 60c6e4d3e17b6f1b63e97610bd10b9cf_

| Criterion | Score | Reasoning |
| --- | --- | --- |
| dashboard_insights_metric_grounding | 1.0 | generated counts are bounded by source counts |
| dashboard_insights_risk_labels | 1.0 | expected risk labels present |
| dashboard_insights_source_grounding | 1.0 | source message IDs are present and allowed |
| dashboard_insights_topic_labels | 1.0 | expected topic labels present |
| dashboard_insights_unanswered_coverage | 1.0 | unanswered output matches seeded unanswered data |

### eca10191b1f39831
_trace: f64ce110779804967d2ac176cafa04cd_

| Criterion | Score | Reasoning |
| --- | --- | --- |
| dashboard_insights_metric_grounding | 1.0 | generated counts are bounded by source counts |
| dashboard_insights_risk_labels | 1.0 | expected risk labels present |
| dashboard_insights_source_grounding | 1.0 | source message IDs are present and allowed |
| dashboard_insights_topic_labels | 1.0 | expected topic labels present |
| dashboard_insights_unanswered_coverage | 1.0 | unanswered output matches seeded unanswered data |

### 50c72f1bf62b2f80
_trace: ebad98d51ade6e6192b6850f293204d1_

| Criterion | Score | Reasoning |
| --- | --- | --- |
| dashboard_insights_metric_grounding | 1.0 | generated counts are bounded by source counts |
| dashboard_insights_risk_labels | 1.0 | expected risk labels present |
| dashboard_insights_source_grounding | 1.0 | source message IDs are present and allowed |
| dashboard_insights_topic_labels | 1.0 | expected topic labels present |
| dashboard_insights_unanswered_coverage | 1.0 | unanswered output matches seeded unanswered data |

