# Implementation Plan: CV × Job Fit CRAG

## Objective

Add a second Q&A demo, reusing the existing corrective RAG (CRAG) infrastructure, that answers questions comparing Tom Proost's CV against the ixor.be "LLM and Agentic AI Engineer" job posting — e.g. "what's a good fit", "what are the caveats", "what's missing".

The existing agent stays untouched in behavior; the codebase is generalized so both agents share one graph, one vectorstore implementation, one API, and one web proxy, differing only by a small per-corpus **profile**.

## 1. Data

```text
data/
  ixor_papers/            (existing, unchanged)
  cv_job_fit/
    job_posting.txt       # ixor.be job ad, "Title: ..." header + body
    cv_tom_proost.txt     # CV text, "Title: ..." header + body
```

- `SimpleVectorStore` already scans a directory of `.txt` files with a `Title:` header and chunks them — no format changes needed, just a new folder.
- **Privacy flag:** the CV text includes phone number, home address, and references' phone numbers. Recommend stripping phone numbers/address from the indexed `.txt` (keep name/email/skills/experience) before this is deployed publicly, since it will be sent to Gemini and retrievable via `/ask` telemetry. Confirm with you before including raw contact details in a public-facing corpus.

## 2. Generalize `src/vectorstore.py`

Replace the single module-level `_vector_store` with a small per-corpus registry:

```python
_CORPUS_DIRS = {
    "ixor_papers": PROJECT_ROOT / "data" / "ixor_papers",
    "cv_job_fit": PROJECT_ROOT / "data" / "cv_job_fit",
}
_stores: dict[str, SimpleVectorStore] = {}

def get_vector_store(corpus: str = "ixor_papers") -> SimpleVectorStore:
    if corpus not in _stores:
        _stores[corpus] = SimpleVectorStore(_CORPUS_DIRS[corpus])
    return _stores[corpus]
```

`SimpleVectorStore` itself needs no changes — chunking/scoring is already corpus-agnostic.

## 3. Add `src/profiles.py` (new, small config module)

Today `nodes.py` hardcodes IXOR-trust vocabulary (`_DOMAIN_TERMS`, `_DOMAIN_SYNONYMS`) and `generate()` hardcodes canned paragraphs about trust/autonomy. Move the corpus-specific bits into a profile so nodes/llm stay generic:

```python
@dataclass(frozen=True)
class AgentProfile:
    corpus: str
    domain_terms: set[str]
    domain_synonyms: dict[str, list[str]]
    generic_rewrite_hints: tuple[str, str]   # attempt-1 / attempt-2+ fallback hints
    llm_instruction: str                     # prompt style for generate_with_llm

PROFILES = {
    "ixor_papers": AgentProfile(...),   # existing constants moved here verbatim
    "cv_job_fit": AgentProfile(
        corpus="cv_job_fit",
        domain_terms={"python", "typescript", "langgraph", "agentic", "llm",
                       "rag", "cloud", "aws", "azure", "fit", "gap", "experience"},
        domain_synonyms={...},  # e.g. "fit": ["match", "experience", "skills"]
        generic_rewrite_hints=(
            "job requirements skills experience responsibilities",
            "candidate background caveats gaps qualifications",
        ),
        llm_instruction=(
            "Answer only from these excerpts comparing a candidate CV against a "
            "job posting. Point out concrete matches and concrete gaps or "
            "caveats. Cite source filenames in square brackets."
        ),
    ),
}
```

## 4. Generalize `src/state.py`

Add one field:

```python
class GraphState(TypedDict):
    ...
    corpus: str   # "ixor_papers" | "cv_job_fit"
```

## 5. Generalize `src/nodes.py`

- `retrieve()`: call `get_vector_store(state["corpus"])`.
- `grade_documents()` / `rewrite_query()`: look up `PROFILES[state["corpus"]]` instead of the module-level `_DOMAIN_TERMS` / `_DOMAIN_SYNONYMS` / hint strings.
- `generate()`: keep the existing IXOR-trust canned-paragraph fallback only for `corpus == "ixor_papers"`. For other corpora (`cv_job_fit`), add one generic **extractive fallback**: rank sentences from retrieved chunks by overlap with the question (reuse the ranking approach already in `llm.py`'s `_context`) and return the top few as the local answer. This avoids writing bespoke canned paragraphs for a second topic and keeps the diff small.

## 6. Generalize `src/llm.py`

- `generate_with_llm(question, documents, profile)` takes the profile's `llm_instruction` instead of the hardcoded IXOR prompt string. Token/finish-reason validation and context-selection logic stay shared and unchanged.

## 7. `src/graph.py` / `src/app.py`

- `run_agent(question: str, corpus: str = "ixor_papers")` threads `corpus` into the initial `GraphState`.
- CLI (`app.py`) gains an optional `--corpus` flag (default unchanged) for local testing of the new agent.

## 8. `src/server.py` (API)

Keep a single generic endpoint rather than duplicating routes:

- `AskRequest` gets `corpus: Literal["ixor_papers", "cv_job_fit"] = "ixor_papers"`.
- Validating against a `Literal`/allow-list prevents path traversal into arbitrary data directories.
- `ask()` passes `request.corpus` to `run_agent(...)`; response shape is unchanged.

## 9. Web layer (`web/`)

Single page, two ask bars — no second page/route needed.

- `web/src/types.ts`: add `corpus?: string` to `AskRequestBody`.
- `web/src/server.ts`: pass `corpus` through to the Python API unchanged (default `"ixor_papers"` if omitted) — no new proxy route needed.
- `web/public/index.html`: add a second section below the existing one, e.g. "Ask about CV × job fit", with its own `<form>`/input/button (`ask-form-fit`, `question-fit`, etc.), its own example chips ("What's a good fit for this role?", "What are the caveats?", "What's missing from the CV for this job?"), and its own answer/telemetry card.
- `web/src/client/app.ts`: generalize the wiring into a small reusable `bindAskForm(config)` helper (form/input/button/status/answer/telemetry element ids + fixed `corpus` value), then call it twice — once for the existing IXOR-papers bar (`corpus: "ixor_papers"`), once for the new CV-fit bar (`corpus: "cv_job_fit"`). Both share the same `/api/ask` POST logic, differing only by `corpus` and DOM element ids.
- `web/public/style.css`: reuse existing card/form styles for the second bar; add a light section divider/heading between the two demos.

## 10. Tests

- `tests/test_vectorstore.py` (new or extended): `get_vector_store` returns distinct, cached stores per corpus; `cv_job_fit` store contains both source files.
- `tests/test_graph_routing.py`: extend/parametrize routing tests to also exercise `corpus="cv_job_fit"` with a small fixture profile, confirming relevance/rewrite use the right domain terms.
- `tests/test_server.py`: add cases for `POST /ask` with `corpus="cv_job_fit"` and an invalid `corpus` value (expect `422`).
- All existing tests must keep passing unmodified in behavior for `corpus="ixor_papers"` (default).

## 11. Rollout order

1. Add `data/cv_job_fit/` files (confirm CV redaction first).
2. Generalize `vectorstore.py`, `state.py`, add `profiles.py`.
3. Refactor `nodes.py` / `llm.py` to use profiles; run full existing test suite to confirm no regression.
4. Add new tests for the `cv_job_fit` corpus.
5. Extend `server.py` API + tests.
6. Extend web proxy types + add the second ask bar to the existing page.
7. Manual QA locally (local mode, then Gemini mode) for both corpora.
8. Deploy (reuses existing Render/Netlify pipeline — no infra changes needed).

## Open question for you

Should the indexed CV text keep the phone number / home address / reference phone numbers, or should I strip them before this becomes a public demo?
