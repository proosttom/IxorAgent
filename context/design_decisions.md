# Design Decisions

## Purpose

IxorAgent is a production-shaped Corrective RAG demo serving two corpora from one codebase: IXOR's public impact papers (`ixor_papers`), and a comparison between Tom Proost's CV and the ixor.be "LLM and Agentic AI Engineer" job posting (`cv_job_fit`). The design prioritizes transparency, deterministic routing, graceful failure, and easy local execution.

## Multi-Corpus Support

Adding the second corpus was done by generalizing the existing pipeline instead of duplicating it:

- `src/vectorstore.py` caches one `SimpleVectorStore` per corpus name (`get_vector_store(corpus)`), keyed against a `CORPUS_DIRS` map. No changes to chunking or scoring were needed.
- `src/profiles.py` introduces `AgentProfile`, moving what used to be IXOR-only hardcoded constants (domain terms, synonyms, rewrite hints, LLM instruction, fallback message) into per-corpus configuration.
- `GraphState` gained a `corpus` field; every node reads it via `state.get("corpus", "ixor_papers")` so existing callers and tests that omit the field keep working unchanged.
- The API (`POST /ask`) exposes `corpus: Literal["ixor_papers", "cv_job_fit"]`, validated against an allow-list to prevent path traversal into arbitrary data directories.
- The web UI reuses one page with two ask bars (one `bindAskForm()` client helper parameterized by corpus and DOM ids) rather than a second page or route.

This kept the diff for the second demo small and left the original corpus's behavior and tests untouched.

## Retrieval

### Local corpus-backed retrieval

The application uses a lightweight local token-overlap retriever instead of requiring a hosted vector database or embedding service.

Reasons:

- The corpus is small and static.
- Retrieval is deterministic and easy to test.
- The demo works without external credentials.
- The retrieval path is easy to explain during a technical demonstration.

This can be replaced by an embedding index when corpus size or semantic search requirements justify the added operational dependency.

### Chunk-level indexing

Papers are split into overlapping chunks before indexing. Search results include the source filename, chunk ID, content, and retrieval score.

Reasons:

- Whole-paper retrieval sends too much irrelevant context to the model.
- Chunks improve evidence precision.
- Chunk metadata supports transparent execution tracing and citations.

### Source diversity

Top-k retrieval prefers one chunk per source before filling remaining result slots with additional chunks.

Reasons:

- Adjacent chunks often contain the same terms and receive identical lexical scores.
- Source diversity gives the language model broader evidence.
- The behavior prevents one paper from monopolizing the context window.

## Relevance Grading

Relevance is evaluated locally before generation. The grader checks meaningful token overlap and retrieval score against the original user question, using the active corpus's `AgentProfile`.

Important rules:

- Rewritten queries cannot make an originally bogus question relevant.
- At least `profile.min_overlap_terms` meaningful overlapping terms are normally required (2 for `ixor_papers`, 1 for `cv_job_fit`).
- A minimum retrieval score is required for multi-term matches.
- The corpus name, `ixor`, is not treated as topical evidence.
- A naive stemmer (`_stem`, strips a trailing "s") lets plural forms like "caveats" match a singular domain term like "caveat".
- For narrow, single-topic corpora, `broad_domain_match` accepts any recognized domain-term hit regardless of question length, since a 2-document corpus has little risk of an unrelated domain term appearing by coincidence.

This is intentionally a deterministic gate first. For `cv_job_fit`, a further optional layer applies: when the lexical gate rejects a question, `use_llm_grading` sends the same retrieved excerpts to Gemini for a bounded structured yes/no second opinion (`grade_relevance_with_llm`, capped at 50 output tokens, temperature 0) before falling back. This rescues naturally phrased synthesis questions ("would you hire this person?") without letting the LLM decide relevance for every request, and without changing the original `ixor_papers` behavior, which remains a pure local safety gate.

## Corrective Routing

The graph follows:

```text
retrieve -> grade -> generate
                   |
                   +-> rewrite -> retrieve, up to two retries
                   |
                   +-> fallback
```

The original question is preserved separately from the rewritten retrieval query. A named retry limit prevents runaway loops.

## Answer Generation

### Optional Gemini synthesis

When `GEMINI_API_KEY` is configured, Gemini is used only for final answer synthesis. Retrieval, grading, context selection, and fallback remain local.

The model receives:

- The original user question.
- Selected evidence sentences.
- Source filenames for citations.
- A concise grounding instruction.

The provider is optional so the project can run offline and tests do not require network access or credentials.

### Deterministic fallback

If Gemini is unavailable, returns an incomplete response, reaches the token limit, or is not configured, the application uses a local generator: the IXOR-specific canned paragraphs for `ixor_papers` (kept as-is to avoid regressing tested behavior), or a generic extractive fallback for other corpora that ranks retrieved sentences by overlap with the question and returns the top few.

Responses are rejected when they are too short, do not end as a complete sentence, or report `MAX_TOKENS`. This prevents truncated model output from reaching the user.

## Context Selection

Context selection ranks sentences by overlap with the question and limits the context sent to Gemini.

Reasons:

- Reduces prompt tokens and latency.
- Limits irrelevant paper metadata.
- Lowers truncation risk.
- Keeps source labels available for citations.

## Transparency and Telemetry

Each graph execution records telemetry in `GraphState`:

- Retrieval attempts and rewritten queries.
- Retrieved sources, chunk IDs, and scores.
- Relevance result.
- Provider and model.
- Context size.
- Prompt, output, and total tokens when supplied by Gemini.

The CLI displays this information next to the answer. API keys are never included in telemetry or output.

## Testing

Tests force local provider mode so they remain deterministic and do not make live LLM calls. Coverage includes:

- Routing and retry limits.
- Corpus retrieval, including per-corpus store isolation and caching.
- Chunk metadata.
- Source diversity.
- Score-aware relevance, including the `cv_job_fit` broadened gate and plural stemming.
- Bogus-question fallback, for both corpora.
- Different answers for different topics.
- Bounded context selection.
- Local generation without an external provider, including the generic extractive fallback.
- API validation of the `corpus` field.

Live Gemini calls (both generation and LLM-based relevance grading) are treated as manual integration checks rather than unit tests.

## Security and Configuration

Secrets are loaded from environment variables or a local `.env` file. `.env` is ignored by Git. The application does not print or store the API key.

Supported configuration includes:

```dotenv
GEMINI_API_KEY=your-api-key
IXOR_LLM_PROVIDER=gemini
IXOR_LLM_MODEL=gemini-2.5-flash
IXOR_LOG_QUESTIONS=true   # default; question text is logged unless set to false
IXOR_LOG_LEVEL=INFO
```

Question logging defaults to on for demo visibility, but is deliberately configurable per the `cv_job_fit` corpus's use of personal CV content — set `IXOR_LOG_QUESTIONS=false` before sharing the URL if that's a concern.

## Known Tradeoffs

- Token overlap is weaker than embedding-based semantic retrieval.
- The deterministic IXOR-papers generator is intentionally narrow; the generic extractive fallback used for other corpora is less polished but avoids writing bespoke canned paragraphs per topic.
- Gemini citation text is requested but not yet independently verified against source filenames.
- The LLM relevance second opinion adds one extra bounded Gemini call per rejected `cv_job_fit` question; acceptable for demo traffic volumes but a cost consideration at scale.
- The in-memory index is rebuilt on first use per corpus and cached in a module-level dict.

## Future Improvements

1. Add citation validation against retrieved source IDs.
2. Persist an embedding index for larger corpora.
3. Add latency and token-cost metrics.
4. Add structured JSON output for API and observability integrations.
5. Add an evaluation set for retrieval precision, answer grounding, and refusal quality.
6. Add further corpora/profiles reusing the same `AgentProfile` pattern.
