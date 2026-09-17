# Serving Plan

## Objective

Make IxorAgent accessible through a public URL for demos while keeping the deployment lightweight, inexpensive, and safe enough for limited external use.

The recommended first deployment is a small HTTP API wrapped around the existing graph. The local CLI remains available for development and offline testing.

## Recommended Demo Architecture

```text
Public HTTPS request
        |
        v
Lightweight web service
        |
        v
run_agent(question)
        |
        +--> local IXOR chunk retrieval
        +--> local relevance grading
        +--> optional Gemini synthesis
        +--> execution telemetry
        |
        v
JSON answer + trace
```

The public service should not expose the local CLI directly. It should expose a narrow API contract and return structured data.

## Target API

### `GET /health`

Returns a cheap readiness response without calling Gemini:

```json
{
  "status": "ok",
  "service": "ixor-agent"
}
```

### `POST /ask`

Request:

```json
{
  "question": "How is trust in AI earned?"
}
```

Response:

```json
{
  "answer": "...",
  "telemetry": {
    "retrieval_steps": [],
    "relevance": {},
    "llm": {}
  }
}
```

The response should include telemetry because transparency is a core demonstration goal. A production version should support a `verbose` flag so public users can receive a reduced trace while the demo view can show full details.

## Web Framework

Use FastAPI with Uvicorn.

Reasons:

- Small implementation surface.
- Automatic OpenAPI documentation.
- Straightforward JSON validation with Pydantic.
- Works well in the existing Python container.
- Easy to test with an in-process client.

Suggested entry point:

```text
src/server.py
```

The server should import and call `run_agent()` rather than duplicate graph logic.

## Deployment Recommendation

### First choice: Render free web service

Deploy the existing Docker image as a public web service.

Advantages:

- Simple Git-based deployment.
- Public HTTPS URL.
- Environment variables and secrets are supported.
- Suitable for an interview or portfolio demonstration.
- No server management for a small demo.

Expected limitation:

- Free instances may sleep when idle, causing cold-start latency on the first request.
- Free-tier availability, limits, and pricing should be checked before presenting the demo as a permanent service.

### Alternative: Google Cloud Run

Cloud Run is a good next step when a pay-per-use container service is preferred. It supports scale-to-zero and HTTPS, but requires a Google Cloud project and billing configuration. It is more production-shaped, but less frictionless for a first free demo.

### Alternative: Hugging Face Spaces

Useful if a small web UI is desired and the project is adapted to Gradio or Streamlit. It is less aligned with the current API-oriented architecture and may require more UI-specific work.

### Alternative: Netlify

Your Netlify account is a good option for the public demo interface, but the current Python application should not be deployed there unchanged.

Recommended Netlify architecture:

```text
Netlify site
  static demo UI
       |
       v
Python API on Render or Cloud Run
  FastAPI -> run_agent()
       |
       +--> local IXOR retrieval
       +--> optional Gemini synthesis
```

Why this is the best Netlify fit:

- Netlify is excellent for a fast public HTTPS frontend.
- The frontend can show the answer and transparency telemetry.
- The Python graph can remain unchanged behind a small FastAPI API.
- Gemini secrets stay on the backend and never reach browser code.
- The frontend can be redeployed independently from the RAG service.

Netlify-specific implementation options:

1. **Static frontend plus Python backend: recommended.** Build a small HTML/JavaScript or React interface on Netlify and configure an environment variable such as `IXOR_API_URL` pointing to the Python service.
2. **Netlify Function proxy.** Add a small JavaScript or TypeScript function that forwards requests to the Python API. This keeps the backend URL private from the UI but adds another deployment component.
3. **Port the backend to a Netlify-native function.** This would require rewriting the Python retrieval and graph code for a supported JavaScript/TypeScript runtime. It is not recommended for this demo because it duplicates working logic and complicates Python dependency handling.

Netlify deployment details:

- Do not put `GEMINI_API_KEY` in Netlify frontend environment variables.
- Use Netlify environment variables only for the public API URL and frontend settings.
- Configure the Python API to allow requests from the Netlify site origin.
- Add a basic demo token or backend authentication before sharing the URL publicly.
- Configure the frontend to display answer text, citations, provider/model, source chunks, latency, and token usage.

Netlify is therefore a strong alternative for the **presentation layer**, while Render or Cloud Run remains the better home for the current Python RAG service.

## Container Changes

The Dockerfile now runs the API server. The CLI remains available locally with `python src/app.py`.

```dockerfile
CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "${PORT:-8000}"]
```

Because JSON-array Docker commands do not expand shell variables, prefer one of these production-safe approaches:

1. Use the Docker shell command that defaults `PORT` to `8000` and executes Uvicorn.
2. Configure the platform start command directly.
3. Use a Python entry point that reads `PORT` and starts Uvicorn.

The service must bind to `0.0.0.0`, not `127.0.0.1`.

## Environment Configuration

Set secrets in the hosting provider's secret manager, never in Git:

```dotenv
GEMINI_API_KEY=...
IXOR_LLM_PROVIDER=gemini
IXOR_LLM_MODEL=gemini-2.5-flash
```

For an offline or cost-free deployment:

```dotenv
IXOR_LLM_PROVIDER=local
```

The `.env` file should remain local and ignored by Git. The public service should use platform-managed environment variables rather than uploading `.env`.

## Security Requirements

Before making the service public:

- Validate request bodies with Pydantic.
- Reject empty questions.
- Enforce a maximum question length, for example 1,000 characters.
- Add a simple per-IP rate limit or platform protection.
- Do not expose `GEMINI_API_KEY` in responses, logs, telemetry, or exception messages.
- Avoid returning raw retrieved document contents by default.
- Keep full trace output limited to source IDs, scores, token counts, and timing.
- Add a basic demo token or HTTP authorization if the URL is shared publicly.
- Configure CORS only for the intended demo frontend.

The service should assume that a public endpoint will be probed with malformed and expensive requests.

## Observability

Implemented in `src/server.py`: every `/ask` request logs one structured stdout line via Python's `logging` module:

```text
ask request_id=<uuid> corpus=<corpus> latency_ms=<ms> relevant=<bool> question=<text|"<redacted>">
```

Configuration:

```dotenv
IXOR_LOG_QUESTIONS=true   # default; set false to redact question text
IXOR_LOG_LEVEL=INFO
```

Question text is logged by default for demo visibility, but stays configurable because the `cv_job_fit` corpus involves personal CV content — set `IXOR_LOG_QUESTIONS=false` before sharing a URL where that's a concern. Failures are logged with `logger.exception(...)`, keeping stack traces out of the HTTP response.

For a first demo, these structured stdout logs are sufficient — a hosted platform (e.g. Render's Logs tab) collects them without adding a separate observability service. Future extensions could add `retrieval_latency_ms` / `llm_latency_ms` breakdowns or stream logs to an external sink for longer retention and search.

## Error Handling

Use clear HTTP responses:

- `200`: answer or safe fallback produced.
- `400`: malformed request or empty question.
- `413`: question exceeds the configured size limit.
- `429`: rate limit exceeded.
- `503`: service is unavailable and no local fallback can answer.
- `500`: unexpected internal error, with details kept out of the public response.

The existing graph fallback should remain a normal answer path rather than being reported as a server error.

## Testing Plan

Add API tests before deployment:

1. `GET /health` returns `200` without an API key.
2. Valid `POST /ask` returns an answer and telemetry.
3. Empty questions return `400`.
4. Oversized questions return `413` or `422`.
5. Bogus questions return the existing safe fallback.
6. Gemini failures fall back locally without leaking exception details.
7. API keys do not appear in response bodies or logs.
8. CORS behavior matches the intended frontend.

Run the existing unit suite and API tests in CI before deployment.

## Deployment Steps

### Phase 1: API wrapper

- Add `src/server.py` with FastAPI app and request/response models.
- Add `/health` and `/ask`.
- Reuse `run_agent()`.
- Add request validation and a request ID.
- Add API tests.

### Phase 2: Local container verification

```bash
docker build -t ixor-agent .
docker run --rm -p 8000:8000 \
  -e IXOR_LLM_PROVIDER=local \
  ixor-agent

curl http://localhost:8000/health
curl -X POST http://localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"How is trust in AI earned?"}'
```

Verify that the container binds externally and that the JSON response includes telemetry.

### Phase 3: Free-tier hosting

- Connect the Git repository to the selected provider.
- Configure the service to build from the Dockerfile.
- Set the provider's web port configuration.
- Add `GEMINI_API_KEY` as a hosted secret if Gemini is enabled.
- Configure a health check for `/health`.
- Deploy with local mode first.
- Enable Gemini only after the public service works without external dependencies.
- Test the public URL with a valid question and a bogus question.

### Phase 4: Demo polish

- Add a small static frontend or hosted API documentation page.
- Show the answer and a collapsible execution trace.
- Display model, sources, retrieval scores, latency, and token usage.
- Add a visible note that the demo uses IXOR public impact papers.
- Keep a local fallback demo command ready in case the free host sleeps or the Gemini quota is unavailable.

## Cost Control

- Keep `top_k` small.
- Keep context sentence selection bounded.
- Keep Gemini output capped at 120 words.
- Use `temperature=0` for repeatable answers.
- Cache identical questions for a short period if usage increases.
- Use local mode for rehearsals and automated checks.
- Set provider-side API spending limits and quotas.
- Avoid calling Gemini for rejected or clearly unsupported questions.

## Recommended First Milestone

Implement the FastAPI wrapper and deploy local mode first. This proves the public service, health checks, validation, telemetry, and container setup without risking Gemini costs or secrets.

Then enable Gemini through the hosting provider's secret configuration and compare:

```text
local mode: deterministic, free, offline-capable
Gemini mode: richer synthesis, token usage, external cost and latency
```

This staged approach keeps the demo available even when the external model is unavailable.
