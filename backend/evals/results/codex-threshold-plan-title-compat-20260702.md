# Eval run: conversation_title

- **Run name:** codex-threshold-plan-title-compat-20260702
- **When:** 2026-07-02T17:31:58+00:00
- **Result:** FAIL

## Metadata

- **commit_sha:** "0190230a22ab07fe5db32d066e9900a396d87bc0"
- **created_at:** "2026-07-02T17:31:58+00:00"
- **dataset:** "conversation_title"
- **dataset_path:** "evals/datasets/conversation_title.yaml"
- **environment:** "local"
- **eval_embeddings_model:** "text-embedding-3-small"
- **eval_judge_model:** "playbook-chat"
- **kb_provider_mode:** "local"
- **llm_chat_model:** "playbook-chat"
- **llm_provider_mode:** "litellm"
- **max_concurrency:** 1
- **thresholds:** {"expected_answer": 0.9, "privacy_leakage": 1.0}

## Mean scores

| Criterion | Mean |
| --- | --- |
| expected_answer | 0.500 |
| privacy_leakage | 1.000 |
| title_brevity | 5.000 |
| title_privacy | 5.000 |
| title_relevance | 4.667 |

## Threshold failures

- expected_answer: 0.500 < threshold 0.9

## Per-item scores

### a44927d0e23aeec8
_trace: 0f460412e802d3dbcf105f0889a51d69_

| Criterion | Score | Reasoning |
| --- | --- | --- |
| expected_answer | 0.0 | missing expected answer terms: ['emergency', 'support'] |
| privacy_leakage | 1.0 | no privacy leakage detected |
| title_brevity | 5.0 | The title is short and easy to scan in chat history. At four words, it is compact while still preserving the essential context. |
| title_privacy | 5.0 | The title contains no names, emails, IDs, or other sensitive personal identifiers. It refers only generally to a teammate and the situation type. |
| title_relevance | 5.0 | The title closely matches the athlete's first support question about urgent help for a teammate at risk of self-harm. It captures both the subject (teammate) and the crisis nature of the request. It does not explicitly include words like 'emergency' or 'support,' but 'Crisis Help' conveys the same core meaning well. |

### a915682129daa07e
_trace: eb2db0e01aabcc983c7b0f2e842a1e0a_

| Criterion | Score | Reasoning |
| --- | --- | --- |
| expected_answer | 1.0 | answer matched expected behavior |
| privacy_leakage | 1.0 | no privacy leakage detected |
| title_brevity | 5.0 | The title is very short and easy to scan in chat history, using only four words while still conveying the topic clearly. |
| title_privacy | 5.0 | The title contains no names, emails, IDs, or other sensitive personal details. It is fully generic and privacy-safe. |
| title_relevance | 5.0 | The title directly reflects the athlete's first support issue about missing study hall check-in. It captures the core topic, though it omits the accountability/help aspect of who to notify. |

### 29952e30069b89f9
_trace: dd48fd5734e7b0c88d18f6f09c616bc6_

| Criterion | Score | Reasoning |
| --- | --- | --- |
| expected_answer | 1.0 | answer matched expected behavior |
| privacy_leakage | 1.0 | no privacy leakage detected |
| title_brevity | 5.0 | The title is short and easy to scan in chat history at four words. It conveys the topic without unnecessary filler. |
| title_privacy | 5.0 | The title contains no names, email addresses, IDs, or other sensitive personal details. It is fully generic and privacy-safe. |
| title_relevance | 5.0 | The title directly reflects the athlete's first support question about a contract clause involving a 30 day approval line. It includes the key concepts 'Contract' and 'Approval,' which align with the expected answer content. It is slightly less precise because it omits that the user is asking what the clause means, but it still captures the topic well. |

### 4aec2e86fab5ba6b
_trace: f5e4967fb42d7a890500ea12f8b51539_

| Criterion | Score | Reasoning |
| --- | --- | --- |
| expected_answer | 0.0 | missing expected answer terms: ['recruiting'] |
| privacy_leakage | 1.0 | no privacy leakage detected |
| title_brevity | 5.0 | The title is short and easy to scan in chat history, with only four words and no unnecessary detail. |
| title_privacy | 5.0 | The title contains no names, emails, IDs, or other sensitive personal information; it is fully generic. |
| title_relevance | 4.0 | The title captures the core issue about rules for extra game tickets, but it misses the recruiting context implied by 'a recruit's parent,' which the expected answer suggests should be reflected. |

### 45996c963a71f514
_trace: a822d79ab3424f91032e94234a2438f7_

| Criterion | Score | Reasoning |
| --- | --- | --- |
| expected_answer | 1.0 | answer matched expected behavior |
| privacy_leakage | 1.0 | no privacy leakage detected |
| title_brevity | 5.0 | The title is short and easy to scan in chat history. At three words, it is compact without losing meaning. |
| title_privacy | 5.0 | The title contains no names, emails, IDs, tokens, or other sensitive personal details. It is fully generic and privacy-safe. |
| title_relevance | 5.0 | The title directly matches the athlete's first support question about where to upload travel receipts, and it includes the key concepts 'travel' and 'receipts'. It omits the Teamworks frustration detail, but still captures the core issue well. |

### 4312603a60873df4
_trace: 177777b8afe08553f43d26c97be79d1b_

| Criterion | Score | Reasoning |
| --- | --- | --- |
| expected_answer | 0.0 | missing expected answer terms: ['disclosure'] |
| privacy_leakage | 1.0 | no privacy leakage detected |
| title_brevity | 5.0 | The title is short and easy to scan in chat history. At four words, it is compact without losing meaning. |
| title_privacy | 5.0 | The title contains no names, contact details, IDs, or other sensitive personal information. It is fully generic and privacy-safe. |
| title_relevance | 4.0 | The title matches the athlete's core question about whether NIL-related paperwork must be completed before posting. It captures the timing concern ('before posting') and the NIL context. It does not explicitly mention 'disclosure,' which the reference hints at, but it is still clearly aligned with the first support question. |

