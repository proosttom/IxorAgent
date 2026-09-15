# IxorAgent Design

## Overview

IxorAgent is a corrective retrieval-augmented generation application over IXOR impact papers. It combines deterministic local retrieval and routing with optional Gemini answer synthesis.

The system is designed to be understandable during a demo:

- Evidence is retrieved locally from the IXOR corpus.
- Evidence is graded before generation.
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
```

### `src/vectorstore.py`

Loads the local IXOR text corpus, splits papers into overlapping chunks, computes token metadata, and returns source-diverse top-k matches with scores.

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

- `retrieve`: searches the current query.
- `grade_documents`: evaluates evidence against the original question.
- `decide_to_generate`: selects generation, rewrite, or fallback.
- `rewrite_query`: adds a neutral IXOR corpus hint and increments retries.
- `generate`: delegates to Gemini when available or uses local deterministic synthesis.
- `fallback`: returns a safe response when evidence is insufficient.

### `src/llm.py`

Optional Gemini integration. It:

1. Selects relevant sentences from retrieved chunks.
2. Caps context size.
3. Sends a grounded prompt to Gemini.
4. Rejects incomplete or truncated responses.
5. Returns provider and usage metadata.
6. Falls back to local generation when unavailable.

## Retrieval Design

The corpus is indexed in memory at process startup. Papers are divided into overlapping chunks to improve evidence precision. Search uses token overlap and returns source-diverse results so one paper does not occupy every result slot.

The current scoring function is intentionally lightweight. It is appropriate for the small demo corpus but can later be replaced by an embedding index without changing the graph contract.

## Relevance Design

Relevance is a local safety gate, not an LLM decision. A document is accepted when it has enough meaningful overlap with the original question and meets the retrieval score threshold.

This protects against a rewritten query making a bogus question appear relevant. For example, `X` remains unsupported even after a retry adds corpus terms.

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

## Validation Strategy

The test suite validates:

- Retrieval and chunk metadata.
- Source diversity.
- Score-aware relevance.
- Rewrite and fallback routing.
- Protection against bogus questions.
- Topic-specific answer differences.
- Local generation without credentials.
- Bounded context selection.

Live Gemini requests are manual integration checks. Unit tests force local mode to remain deterministic and avoid network or credential dependencies.

## Extension Points

The design supports future improvements without changing the CLI or graph contract:

- Replace lexical search with embeddings.
- Persist the retrieval index.
- Validate citations against retrieved source IDs.
- Expose telemetry as structured JSON or metrics.
- Add conversation history and follow-up question handling.
- Add a benchmark set for retrieval and answer grounding.
