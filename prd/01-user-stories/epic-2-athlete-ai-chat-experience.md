# Epic 2: Athlete AI Chat Experience

## Epic Goal

Give athletes a fast, simple, trustworthy chat experience for NIL, compliance, and athletic department process questions.

### US-05
As an athlete
I want a chat-first home screen
So that I can immediately ask Playbook for help.

> **New in Playbook MVP.** The primary athlete experience is a simple chat surface.

#### Acceptance Criteria
1. The authenticated athlete home route renders a chat input as the primary focus.
2. The screen includes a conversation history sidebar.
3. The screen includes an upload button.
4. The screen remains usable on standard desktop and responsive web viewports.
5. Empty state content does not imply affiliation with any specific university.

### US-06
As an athlete
I want to ask NIL, compliance, and process questions
So that I can get quick guidance from athletic department knowledge.

> **New in Playbook MVP.** Initial questions include "How do I do X?", "Can I do Y?", and "Where do I upload Z?"

#### Acceptance Criteria
1. The athlete can submit a natural-language question.
2. The backend creates a conversation message record before generation starts.
3. The answer is generated through the Playbook chat agent.
4. The answer uses available knowledgebase context for policy and process guidance.
5. The answer is direct, concise, and warm.
6. The final response is saved to conversation history.

### US-07
As an athlete
I want answers to stream as they are generated
So that Playbook feels responsive while the agent works.

> **New in Playbook MVP.** Streaming is required for perceived quality.

#### Acceptance Criteria
1. Chat generation emits incremental response chunks to the frontend.
2. The UI renders streamed text without blocking the input shell.
3. If streaming fails, the conversation displays a recoverable error state.
4. Completed streamed output is persisted as the final assistant message.

### US-08
As an athlete
I want answers to include source citations
So that I can see which department documents support the answer.

> **New in Playbook MVP.** Citations should appear at the bottom of answers.

#### Acceptance Criteria
1. Every grounded answer includes citations at the bottom.
2. Each citation shows the source document title.
3. Citation metadata links the answer to retrieved chunks or document records.
4. If no source supports a policy/process answer, the agent declines instead of fabricating a citation.
5. Citation rendering remains readable in conversation history.

### US-09
As an athlete
I want to upload supported files into a chat
So that Playbook can consider my document or screenshot-like material in that conversation.

> **New in Playbook MVP.** Athlete uploads are conversation-scoped, not shared KB documents.

#### Acceptance Criteria
1. The chat upload control accepts supported document types: PDF, DOCX, PPTX, and XLSX.
2. Uploaded files are attached to the active conversation.
3. Uploaded file content can be used for that conversation's answer context.
4. Uploaded files are retained and visible in conversation history.
5. Athlete-uploaded files are not added to the shared knowledgebase.

### US-10
As an athlete
I want to see my full conversation history
So that I can return to previous Playbook answers.

> **New in Playbook MVP.** Full history is required for the prototype.

#### Acceptance Criteria
1. The history sidebar lists prior conversations for the signed-in athlete.
2. Selecting a conversation loads messages, citations, and retained file attachments.
3. Athletes can only view their own conversations.
4. New messages append to the selected conversation.
5. History retrieval is paginated or otherwise bounded to avoid slow initial loads.

### US-11
As an athlete
I want Playbook to decline questions it should not answer
So that I am not misled on sensitive or unsupported topics.

> **New in Playbook MVP.** Unknown or unsafe answers should direct athletes to the athletic department.

#### Acceptance Criteria
1. The agent declines when it lacks sufficient KB support for policy/process guidance.
2. The agent declines medical, legal, mental-health, harassment/reporting, emergency, and recruiting-risk advice outside approved guidance.
3. Declines tell the athlete to contact the athletic department.
4. Emergency-related messages refuse advice and show emergency instructions.
5. Declines are stored for admin analytics.

## Edge Cases

| Edge Case | Expected Behavior |
|-----------|-------------------|
| No KB results are retrieved | Agent declines and directs user to athletic department |
| File upload succeeds but extraction fails | User sees file-specific error; chat remains usable |
| Streaming disconnects | UI shows recoverable state and persists any completed final response only |
| Athlete opens another user's conversation URL | Access is denied |
