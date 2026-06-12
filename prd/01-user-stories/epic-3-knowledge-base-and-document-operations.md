# Epic 3: Knowledge Base and Document Operations

## Epic Goal

Give admins enough document operations to make Playbook useful while keeping the prototype simple: upload, process, tag, retry, and make content searchable for all athletes.

### US-12
As an admin
I want to upload department documents
So that athletes can receive answers from current athletic department knowledge.

> **New in Playbook MVP.** Documents include compliance materials, manuals, handbooks, coaching content, and system process instructions.

#### Acceptance Criteria
1. Admins can upload supported KB documents.
2. Uploaded documents become eligible for processing immediately.
3. The system records uploader, filename, size, content type, and upload timestamp.
4. Failed uploads return a clear error and do not create ready documents.
5. Upload actions are recorded in the audit log.

### US-13
As an admin
I want to see document processing status
So that I know whether uploaded content is ready for athlete answers.

> **New in Playbook MVP.** Status states should include uploaded, processing, ready, and failed.

#### Acceptance Criteria
1. Uploaded documents show `uploaded` before processing starts.
2. Documents show `processing` during parse, chunk, embed, and load stages.
3. Documents show `ready` after searchable vectors are available.
4. Documents show `failed` when extraction or indexing fails.
5. Failed status includes a clear reason when available.

### US-14
As an admin
I want failed documents to be retryable
So that bad extraction or no-text failures can be corrected.

> **New in Playbook MVP.** Admins can retry or re-upload failed documents.

#### Acceptance Criteria
1. A failed document exposes retry or re-upload actions.
2. Retrying restarts the processing pipeline.
3. Re-uploading preserves audit history of the replacement action.
4. A no-text extraction failure is marked failed with a clear message.
5. Athletes do not receive answers from failed documents.

### US-15
As an admin
I want metadata tags for documents
So that retrieval and citations can expose current source context.

> **New in Playbook MVP.** Metadata tags are preferred over a hard category taxonomy.

#### Acceptance Criteria
1. Admins can assign metadata tags to documents.
2. Tags support source and freshness concepts.
3. Retrieval stores and returns metadata needed for ranking and citations.
4. Admin-uploaded shared KB documents are official by definition for MVP.
5. Metadata changes are recorded in the audit log.

### US-16
As an admin
I want all MVP documents visible to all athletes
So that the prototype stays simple while preserving an extensible access model.

> **New in Playbook MVP.** Future access may vary by sport, team, or audience.

#### Acceptance Criteria
1. MVP KB documents are visible to all athletes by default.
2. The document model includes fields or structure that can support future audience rules.
3. Retrieval filters enforce the active visibility rule.
4. Future team/sport visibility can be added without replacing the document table.

### US-17
As an athlete
I want Playbook to use the newest source when documents conflict
So that answers reflect current department guidance.

> **New in Playbook MVP.** Newest source is the default conflict rule.

#### Acceptance Criteria
1. Retrieved context includes document freshness metadata.
2. When sources conflict, the agent prefers the newest applicable document by default.
3. Admin-official status and priority do not override freshness in MVP.
4. If conflict remains unresolved, the agent explains the conflict and directs the athlete to the athletic department.

## Edge Cases

| Edge Case | Expected Behavior |
|-----------|-------------------|
| Document has no extractable text | Mark failed and show reason |
| Admin uploads duplicate file | Deduplication or duplicate warning prevents confusing source records |
| Document metadata changes while ingestion is running | Metadata update is saved and applied when document becomes ready |
| Future sport/team visibility is added | Existing all-athlete docs continue to work |
