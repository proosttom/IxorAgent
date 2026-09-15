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
- Optional grounded answer synthesis through an external small LLM

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
/usr/local/bin/python3 src/app.py "How can IXOR earn users' trust in agentic AI?"
```

By default, the app uses its deterministic local generator and does not need an API key. To enable Gemini for answer synthesis, install the requirements and configure:

```bash
export IXOR_LLM_PROVIDER=gemini
export GEMINI_API_KEY="your-api-key"
export IXOR_LLM_MODEL=gemini-2.0-flash
/usr/local/bin/python3 src/app.py "How can IXOR earn users' trust in agentic AI?"
```

Retrieval and relevance grading remain local. Gemini receives only relevant retrieved excerpts, must cite their source filenames, and falls back to the deterministic generator if the provider is unavailable.

Alternatively, place these settings in a local `.env` file. The file should not be committed:

```dotenv
IXOR_LLM_PROVIDER=gemini
GEMINI_API_KEY=your-api-key
IXOR_LLM_MODEL=gemini-2.0-flash
```

You can pass any question as a command-line argument to query the IXOR corpus dynamically.

If you run the app without arguments, it enters an interactive loop and keeps asking for questions until you type `exit`, `quit`, or `q`.

### Example questions

```bash
/usr/local/bin/python3 src/app.py "What does IXOR say about transparency and trust in agentic AI?"
/usr/local/bin/python3 src/app.py "When should an organization avoid using an agent?"
/usr/local/bin/python3 src/app.py "What is IXOR's view on autonomy vs accountability?"
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
