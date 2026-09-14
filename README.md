# IXOR CRAG Agent

A compact corrective RAG prototype built around IXOR's impact papers on trust, autonomy, and agentic AI.

## Architecture

```text
[User Question]
      |
      v
[Retrieve from IXOR corpus]
      |
      v
[Grade relevance]
      |
      +--> relevant --> [Generate grounded answer]
      |
      +--> irrelevant + retry < 2 --> [Rewrite Query] -> [Retrieve]
      |
      +--> retry >= 2 --> [Fallback]
```

## What it demonstrates

- Local knowledge retrieval from IXOR source material
- Relevance grading before generation
- Query rewriting when evidence is weak
- Safe fallback behavior when retries are exhausted

## Project layout

```text
.
├── data/
│   ├── ixor_impact_papers.txt
│   └── ixor_papers/
├── src/
│   ├── app.py
│   ├── graph.py
│   ├── nodes.py
│   ├── state.py
│   └── vectorstore.py
├── tests/
│   └── test_graph_routing.py
├── Dockerfile
├── requirements.txt
├── pytest.ini
└── README.md
```

## Run

```bash
/usr/local/bin/python3 src/app.py
```

## Test

```bash
/usr/local/bin/python3 -m pytest -q
```

## Docker

```bash
docker build -t ixor-crag-agent .
docker run --rm ixor-crag-agent
```

This demo is designed to show a reliable, testable CRAG pattern: fetch only IXOR-relevant context, validate it, and answer with guardrails instead of unbounded generation.
