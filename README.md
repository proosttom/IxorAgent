# IXOR CRAG Agent

A compact corrective RAG prototype built around IXOR's impact papers on trust, autonomy, and agentic AI.

## Tech Stack

| Technology | Role |
| --- | --- |
| **Python 3.13** | Core language for the CRAG graph, retrieval, and API. |
| **FastAPI** | HTTP API (`/health`, `/ask`) with Pydantic request/response validation. |
| **Uvicorn** | ASGI server running the FastAPI app. |
| **Custom LangGraph-style state graph** | Deterministic retrieve → grade → generate/rewrite/fallback routing (`src/graph.py`, `src/nodes.py`). |
| **Google Gemini API** (`google-genai`) | Optional grounded answer synthesis and LLM-assisted relevance grading; the app runs fully offline without it. |
| **pytest** | Unit tests for routing, retrieval, relevance grading, and the API. |
| **Node.js / Express** | Same-origin proxy and static host for the browser UI (`web/src/server.ts`). |
| **TypeScript** | Typed server and client code, compiled separately for Node and the browser. |
| **Netlify Functions** | Alternative serverless deployment target for the same Express app. |
| **Docker** | Container image for the Python API, used for Render/Cloud Run deployment. |

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
├── web/                      # Node.js/Express frontend, styled after ixor.be
│   ├── server.js
│   ├── public/
│   └── netlify/functions/
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
docker run --rm -p 8000:8000 \
      -e IXOR_LLM_PROVIDER=local \
      ixor-crag-agent

curl http://localhost:8000/health
curl -X POST http://localhost:8000/ask \
      -H 'Content-Type: application/json' \
      -d '{"question":"How is trust in AI earned?"}'
```

## Web frontend (Node.js/Express + TypeScript)

A small Express server, written in TypeScript, serves an IXOR-styled UI and proxies `/api/ask` and `/api/health` to the Python API, so the browser never talks to the backend directly.

```bash
cd web
npm install
cp .env.example .env   # set IXOR_API_URL to your deployed Python API
npm run build           # compiles src/*.ts -> dist/ and src/client/app.ts -> public/app.js
node dist/server.js
```

`npm start` and `npm run dev` both build first, then run the compiled server.
node server.js
```

Open `http://localhost:3000`. The page shows the answer plus a collapsible **Execution details** panel with retrieval hits, relevance, provider/model, and token usage.

The same Express app can deploy as:

- A standalone Node service (Render, Railway, Fly.io), or
- Netlify Functions (`web/netlify/functions/api.js` + `netlify.toml`, using your existing Netlify account).

This demo is designed to show a reliable, testable CRAG pattern: fetch only IXOR-relevant context, validate it, and answer with guardrails instead of unbounded generation.
