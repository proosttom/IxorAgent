# Design Decisions

## Purpose

IxorAgent is a production-shaped Corrective RAG demo over IXOR impact papers. The design prioritizes transparency, deterministic routing, graceful failure, and easy local execution.

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

Relevance is evaluated locally before generation. The grader checks meaningful token overlap and retrieval score against the original user question.

Important rules:

- Rewritten queries cannot make an originally bogus question relevant.
- At least two meaningful overlapping terms are normally required.
- A minimum retrieval score is required for multi-term matches.
- The corpus name, `ixor`, is not treated as topical evidence.

This is intentionally a deterministic POC grader. A model-based structured grader can be added later, but it should remain behind the local safety and retry boundaries.

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

If Gemini is unavailable, returns an incomplete response, reaches the token limit, or is not configured, the application uses the deterministic local generator.

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
- Corpus retrieval.
- Chunk metadata.
- Source diversity.
- Score-aware relevance.
- Bogus-question fallback.
- Different answers for different topics.
- Bounded context selection.
- Local generation without an external provider.

Live Gemini calls are treated as manual integration checks rather than unit tests.

## Security and Configuration

Secrets are loaded from environment variables or a local `.env` file. `.env` is ignored by Git. The application does not print or store the API key.

Supported configuration includes:

```dotenv
GEMINI_API_KEY=your-api-key
IXOR_LLM_PROVIDER=gemini
IXOR_LLM_MODEL=gemini-2.5-flash
```

## Known Tradeoffs

- Token overlap is weaker than embedding-based semantic retrieval.
- The deterministic generator is intentionally narrow.
- Gemini citation text is requested but not yet independently verified against source filenames.
- Telemetry is currently CLI-oriented rather than exported as structured logs or metrics.
- The in-memory index is rebuilt at process startup.

## Future Improvements

1. Add citation validation against retrieved source IDs.
2. Persist an embedding index for larger corpora.
3. Add latency and token-cost metrics.
4. Add structured JSON output for API and observability integrations.
5. Add an evaluation set for retrieval precision, answer grounding, and refusal quality.
