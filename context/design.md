# IxorAgent Design

## Overview

IxorAgent is a corrective retrieval-augmented generation application that serves two demos from one codebase:

- `ixor_papers`: Q&A over IXOR's public impact papers.
- `cv_job_fit`: comparing Tom Proost's CV against the ixor.be "LLM and Agentic AI Engineer" job posting (fit, gaps, caveats).

Both combine deterministic local retrieval and routing with optional Gemini answer synthesis, differing only by a small per-corpus `AgentProfile` (see `src/profiles.py`).

The system is designed to be understandable during a demo:

- Evidence is retrieved locally from the selected corpus.
- Evidence is graded before generation, with an optional LLM second opinion.
- Weak evidence triggers bounded query rewriting.
- Unsupported questions receive a fallback response.
- Execution details are shown beside the answer.

## System Flow

```text
+----------------+
| User question  |
+-------+--------+
        |
        v
+----------------+
| Retrieve       |  Search chunked IXOR corpus
+-------+--------+
        |
        v
+----------------+
| Grade          |  Token overlap + retrieval score
+---+--------+---+
    |        |
    |        +-----------------------------+
    |                                      |
 relevant                              irrelevant
    |                                      |
    v                                      v
+----------------+                 +----------------+
| Select context |                 | Rewrite query  |
+-------+--------+                 +-------+--------+
        |                                  |
        v                                  |
+----------------+                          |
| Generate       | <------------------------+
| Gemini/local   |       max two retries
+-------+--------+
        |
        v
+----------------+
| Answer + trace |
+----------------+
```

## Components

### `src/app.py`

CLI entry point. It supports:

- One-shot questions passed as command-line arguments.
- An interactive question loop.
- Answer display.
- Execution telemetry display.

### `src/graph.py`

Orchestrates one request through the corrective RAG loop. It initializes `GraphState`, invokes retrieval and grading, applies routing decisions, and stops after generation or fallback.

### `src/state.py`

Defines the request state shared by all nodes:

```text
question          Current retrieval query
original_question User's unchanged question
documents         Retrieved corpus chunks
retry_count       Number of rewrite attempts
generation        Final answer text
is_relevant       Relevance gate result
telemetry         Retrieval, grading, provider, and token metadata
corpus            Which corpus/profile to use ("ixor_papers" | "cv_job_fit")
```

### `src/profiles.py`

Defines `AgentProfile`, the per-corpus configuration that keeps `nodes.py`/`llm.py` corpus-agnostic:

```text
corpus              corpus/data directory key
domain_terms        topical vocabulary used by the relevance gate
domain_synonyms     expansion terms used by query rewriting
rewrite_hints       generic hints for retry attempt 1 / attempt >=2
llm_instruction     prompt style passed to Gemini generation
fallback_message    safe response when evidence is insufficient
min_overlap_terms   overlapping terms required for a lexical relevance match
broad_domain_match  accept any domain-term hit regardless of question length
use_llm_grading     ask Gemini for a second opinion when the lexical gate rejects
```

`get_profile(corpus)` returns the matching profile, defaulting to `ixor_papers`.

### `src/vectorstore.py`

Loads a local text corpus, splits papers into overlapping chunks, computes token metadata, and returns source-diverse top-k matches with scores. Stores are cached per corpus by `get_vector_store(corpus)`, keyed against `CORPUS_DIRS` (`data/ixor_papers`, `data/cv_job_fit`).

Each retrieved result contains:

```text
source
 title
chunk_id
page_content
score
```

### `src/nodes.py`

Contains the graph nodes:

- `retrieve`: searches the current query against the state's corpus.
- `grade_documents`: evaluates evidence against the original question using the corpus's `AgentProfile`; when the lexical check rejects and `use_llm_grading` is set, asks the LLM for a second opinion before giving up.
- `decide_to_generate`: selects generation, rewrite, or fallback.
- `rewrite_query`: expands recognized domain terms (or a generic hint) and increments retries.
- `generate`: delegates to Gemini when available; otherwise uses the IXOR-specific canned local synthesis for `ixor_papers`, or a generic extractive sentence-ranking fallback for other corpora.
- `fallback`: returns the profile's safe response when evidence is insufficient.

### `src/llm.py`

Optional Gemini integration. It:

1. Selects relevant sentences from retrieved chunks.
2. Caps context size.
3. Sends a grounded prompt to Gemini, using the active profile's instruction text.
4. Rejects incomplete or truncated responses.
5. Returns provider and usage metadata.
6. Falls back to local generation when unavailable.

It also exposes `grade_relevance_with_llm()`, a bounded structured-output call (`GradeDocuments` schema, low token cap, no thinking budget) used as the second-opinion relevance check described above.

## Retrieval Design

Each corpus is indexed in memory on first use and cached per corpus name. Papers are divided into overlapping chunks to improve evidence precision. Search uses token overlap and returns source-diverse results so one paper does not occupy every result slot.

The current scoring function is intentionally lightweight. It is appropriate for the small demo corpora but can later be replaced by an embedding index without changing the graph contract.

## Relevance Design

Relevance is primarily a local, deterministic safety gate: a document is accepted when it has enough meaningful token overlap with the original question (a naive stemmer matches plurals like "caveats" against domain terms like "caveat") and meets the retrieval score threshold.

This protects against a rewritten query making a bogus question appear relevant. For example, `X` remains unsupported even after a retry adds corpus terms.

For narrow, single-topic corpora (`cv_job_fit`), the profile loosens this gate — a single domain-term hit is enough evidence (`broad_domain_match`) — and, when the lexical check still rejects the question, `grade_relevance_with_llm()` gives the LLM a bounded, context-grounded second opinion before falling back. This rescues naturally phrased questions ("would you hire this person?") that share no literal wording with the corpus, while still rejecting genuinely unrelated questions.

## Generation Design

The generation boundary is explicit:

```text
retrieved evidence + accepted relevance
                    |
                    v
       optional Gemini synthesis
                    |
             validated answer
```

Gemini is never responsible for retrieving documents or deciding whether the original question is supported. It only synthesizes accepted evidence.

When Gemini is not configured or fails, the deterministic local generator keeps the demo usable offline.

## Transparency Model

Every request records an execution trace in `GraphState["telemetry"]`:

```text
retrieval_steps
  query
  source
  chunk_id
  score

relevance
  is_relevant
  question_terms
  graded_by      "lexical" or "llm"

llm
  provider
  model
  context_chars
  prompt_tokens
  output_tokens
  total_tokens
  finish_reason
```

The CLI renders this trace next to the answer. API keys are not included in state or output.

Each `/ask` request also logs a structured stdout line (`request_id`, `corpus`, `latency_ms`, `relevant`, `question`) from `src/server.py`. Question text is logged by default; set `IXOR_LOG_QUESTIONS=false` to redact it.

## Failure Handling

The system returns a fallback when:

- No documents are retrieved after retries.
- Retrieved evidence fails the relevance gate.
- The retry limit is reached.
- Gemini is not configured.
- The Gemini request fails.
- Gemini returns an incomplete or token-truncated response.

The retry limit is defined centrally as `MAX_RETRIES = 2`.

## Runtime Configuration

Local mode requires no external service:

```dotenv
IXOR_LLM_PROVIDER=local
```

Gemini mode can be enabled through `.env`:

```dotenv
GEMINI_API_KEY=your-api-key
IXOR_LLM_PROVIDER=gemini
IXOR_LLM_MODEL=gemini-2.5-flash
```

If `GEMINI_API_KEY` is present and no provider is explicitly configured, the application selects Gemini automatically.

Request logging is configurable independently of the LLM provider:

```dotenv
IXOR_LOG_QUESTIONS=true   # default; set false to redact question text in logs
IXOR_LOG_LEVEL=INFO
```

## Validation Strategy

The test suite validates:

- Retrieval and chunk metadata, per corpus.
- Source diversity.
- Score-aware relevance, including the `cv_job_fit` broadened gate and plural domain-term stemming.
- Rewrite and fallback routing.
- Protection against bogus questions.
- Topic-specific answer differences.
- Local generation without credentials, including the generic extractive fallback for non-IXOR corpora.
- Bounded context selection.
- API validation of the `corpus` field (invalid values rejected).

Live Gemini requests (generation and LLM-based relevance grading) are manual integration checks. Unit tests force local mode to remain deterministic and avoid network or credential dependencies.

## Extension Points

The design supports future improvements without changing the CLI or graph contract:

- Replace lexical search with embeddings.
- Persist the retrieval index.
- Validate citations against retrieved source IDs.
- Expose telemetry as structured JSON or metrics.
- Add conversation history and follow-up question handling.
- Add a benchmark set for retrieval and answer grounding.
- Add further corpora/profiles beyond `ixor_papers` and `cv_job_fit`.
