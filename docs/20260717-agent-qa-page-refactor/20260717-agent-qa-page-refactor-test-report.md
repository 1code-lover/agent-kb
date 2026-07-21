# 20260717-agent-qa-page-refactor-test-report

## 1. Result

Passed.

The `/agent` page now works as a question-first workspace with three usable modes:
1. basic chat,
2. KB-scoped chat,
3. Agent advanced mode.

This round also fixed a blocking backend regression: historical bad embeddings and empty Markdown nodes could cause `/api/chat/query` to return HTTP 400. After the fix, browser-based KB chat now returns answers and sources normally.

---

## 2. Main changes under test

### 2.1 Front-end page refactor
- `webapp/src/pages/AgentPage.jsx`
- `webapp/src/pages/agent-page.css`
- `webapp/src/components/ShellLayout.jsx`

Verified behavior:
- `/agent` exposes three top-level experiences;
- KB chat requires an explicit active KB selection;
- chat thread, current scope, model status, and latest sources are visible in one page;
- the sidebar label is now `??`.

### 2.2 Retriever hardening
- `server/retriever.py`
- `tests/api/test_retriever_stale_vectors.py`

Verified behavior:
- wrong-dimension embeddings are pruned before vector retrieval;
- BM25 build skips empty or unserializable nodes from historical imports;
- `kb_ids` are pushed down as metadata filters during retrieval.

---

## 3. Command execution record

### 3.1 Node rule tests
```powershell
node --test webapp/src/domain/agentExperience.test.js webapp/src/api/response.test.js webapp/src/domain/kbSelection.test.js
```
Result: 14/14 passed.

### 3.2 Front-end build
```powershell
cd webapp
npm run build
```
Result: passed.

### 3.3 Targeted backend regression
```powershell
pytest tests/api/test_retriever_stale_vectors.py -q
```
Result: 7 passed.

Coverage added in this file:
- stale vector id pruning,
- incompatible embedding pruning,
- KB metadata filter propagation,
- BM25-compatible node filtering before retriever build.

### 3.4 Format gate
```powershell
git diff --check
```
Result: exit code 0. Only LF/CRLF warnings were printed; no whitespace errors.

---

## 4. Direct HTTP verification

Request:
```json
{
  "question": "CDI product line whitepaper: from what number to what number did CFDI average size change?",
  "session_id": "desktop-default-chat-20260716",
  "kb_ids": ["20260716"]
}
```

Endpoint:
`POST http://127.0.0.1:18080/api/chat/query`

Result:
- HTTP 200
- `answer` returned normally
- `sources` included `CDI???????_c5778ffb.md`
- the previous 400 regression no longer reproduced

---

## 5. Browser smoke

Target page: `http://127.0.0.1:5173/agent`

### 5.1 Structure smoke
Verified:
- default tab is basic chat;
- user can switch to KB chat;
- user can switch to Agent advanced mode;
- scope summary, model status, and latest sources area are visible.

### 5.2 KB-scoped chat smoke
Steps:
1. open `/agent`;
2. switch to `?????`;
3. choose `??????20260716?`;
4. ask: `CDI?????????CFDI ???????????????????????`

Observed result:
- the page returned `337MB ? 202MB`;
- the conversation thread appended both user message and assistant answer;
- the `??????` panel showed 4 sources;
- no HTTP 400 surfaced in the UI.

---

## 6. Remaining non-blocking issues

1. KB `20260716` is still a smoke dataset with empty Markdown files, filename experiments, and temporary samples.
2. Because the dataset is noisy, the source list can still include low-value or empty documents.
3. Formal QA should use `grain-knowledge-base` or a cleaned/reimported KB.

---

## 7. Acceptance summary

This topic is ready to move forward:
- the `/agent` page interaction target is met;
- basic chat, KB chat, and Agent advanced mode all work;
- explicit KB selection protection works;
- the historical 400 regression is fixed;
- automated checks, direct HTTP verification, browser smoke, and format gate all passed.
