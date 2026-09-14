# IXOR CRAG Agent

A lean proof-of-concept for a corrective RAG pattern built around a minimal state machine.

## Architecture

```text
[User Question]
      |
      v
[Retrieve] -> [Grade Documents]
      |
      +--> relevant --> [Generate]
      |
      +--> irrelevant + retry < 2 --> [Rewrite Query] -> [Retrieve]
      |
      +--> retry >= 2 --> [Fallback]
```

## Core idea

- Retrieve candidate context from a local knowledge base.
- Grade relevance before generation.
- Rewrite the query when evidence is weak.
- Stop with a controlled fallback if retries are exhausted.

## Run

```bash
pytest
```
