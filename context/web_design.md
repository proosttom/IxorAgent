# Web Frontend & Serving Design

## Objective

Document the actual implemented architecture for serving IxorAgent through a browser-facing demo, styled after ixor.be, using Node.js/Express and TypeScript as the presentation-layer stack.

This complements `serve_plan.md` (Python API deployment) and `design.md` (RAG architecture). This file covers the frontend/proxy layer added on top of those.

## Architecture

```text
Browser (IXOR-styled UI)
        |
        v
Node.js / Express (TypeScript)
  web/src/server.ts
        |
        +--> GET  /api/health  --> proxies to Python API /health
        +--> POST /api/ask     --> proxies to Python API /ask
        |
        v
Python FastAPI service (Render)
  src/server.py -> run_agent()
        |
        +--> local IXOR chunk retrieval
        +--> local relevance grading
        +--> optional Gemini synthesis
        +--> execution telemetry
```

The browser never talks to the Python API directly. The Node layer is a thin, same-origin proxy, which avoids CORS complexity on the frontend and keeps the backend URL out of client-side code.

## Why a Node proxy instead of calling the Python API directly from the browser

- Keeps `IXOR_API_URL` server-side, not hardcoded into shipped JS.
- Centralizes request validation (empty question, length limit) before it reaches the Python API.
- Adds a rate limiter (`express-rate-limit`) in front of the more expensive Python path.
- Gives a natural place to add auth, caching, or logging later without touching the Python service.
- Matches the "static frontend + backend API" pattern recommended in `serve_plan.md` for Netlify.

## Directory Layout

```text
web/
├── src/
│   ├── server.ts          # Express app: static hosting + /api/* proxy
│   ├── types.ts           # Shared request/response contracts
│   └── client/
│       └── app.ts         # Browser script (compiled to public/app.js)
├── public/
│   ├── index.html         # IXOR-styled landing page
│   └── style.css
├── netlify/
│   └── functions/
│       └── api.ts         # Wraps the Express app for Netlify Functions
├── tsconfig.json           # Server build (CommonJS, Node lib)
├── tsconfig.client.json    # Browser build (DOM lib, no module system)
├── package.json
└── .env.example
```

Build artifacts (`dist/`, `public/app.js`) are gitignored; only TypeScript sources are committed.

## Styling Decisions

Visual style was captured directly from ixor.be and translated into CSS variables:

```text
--cream:      #f4f1ea   background
--ink:        #1a1a1a   body text
--mint:       #5cb896   primary accent / CTA buttons
--mint-dark:  #3f8f72   hover state
--border:     #d8d3c7   card/input borders
```

Conventions matched from the source site:

- Bold, lowercase wordmark in the header.
- Mint-green banner strip at the very top.
- Solid mint CTA buttons with bold uppercase white text, square corners.
- Cream page background with white content cards.
- Condensed, bold sans-serif for headings and buttons.

The page is not a copy of ixor.be markup — only the visual language (palette, type weight, button style) was reproduced, applied to an original layout for the Q&A demo.

## API Contract (Node layer)

### `GET /api/health`

Proxies to the Python `/health` endpoint. Returns `503` with a synthetic body if the upstream is unreachable, instead of crashing.

### `POST /api/ask`

Request:

```json
{ "question": "How is trust in AI earned?" }
```

Validation performed in Node before proxying:

- Rejects empty/whitespace-only questions (`400`).
- Rejects questions over 1,000 characters (`413`).
- Rate-limited to 20 requests/minute per client (`429` via `express-rate-limit`).

Response is passed through from the Python API unchanged, so the frontend always renders the same `answer` + `telemetry` shape documented in `design.md`.

## TypeScript Usage

Two separate `tsconfig` files are used because the server and browser code target different runtimes:

- `tsconfig.json`: `module: CommonJS`, no DOM lib, compiles `src/server.ts` and `src/types.ts` to `dist/`.
- `tsconfig.client.json`: `lib: DOM`, no module system, compiles `src/client/app.ts` to `public/app.js` for direct `<script>` inclusion.

Shared request/response types (`AskRequestBody`, `AskResponseBody`, `Telemetry`, etc.) live in `src/types.ts` and are imported by the server; the client script defines its own minimal local interfaces to avoid coupling the browser bundle to server-only types.

## Deployment Paths

### Standalone Node service

```bash
cd web
npm install
npm run build
node dist/server.js
```

Deployable to Render, Railway, or Fly.io as a second service alongside the Python API.

### Netlify (Functions)

`netlify.toml` (repo root) configures:

```toml
[build]
  base = "web"
  publish = "public"
  functions = "netlify/functions"
  command = "npm install && npm run build"

[[redirects]]
  from = "/api/*"
  to = "/.netlify/functions/api/:splat"
  status = 200
```

`netlify/functions/api.ts` wraps the same Express app via `serverless-http`, so the identical route logic runs both as a long-lived Node process and as a Netlify Function, with no duplicated business logic.

## Environment Configuration

```dotenv
IXOR_API_URL=https://ixoragent.onrender.com
PORT=3000
```

`.env` is loaded relative to `__dirname` (not `process.cwd()`) so the server behaves consistently regardless of where `node` is invoked from — this was a real bug encountered during local testing and fixed by pinning the dotenv path.

## Known Tradeoffs

- The Node layer duplicates minimal validation already enforced by the Python API (defense in depth, not a bug).
- No caching layer yet; identical questions still hit Gemini/local generation each time.
- No authentication on the public demo; acceptable for a portfolio/interview demo, not for unrestricted public traffic.
- Visual styling is hand-matched from screenshots, not pulled from a design system or shared tokens with ixor.be.

## Future Improvements

1. Add a shared `openapi.json`-derived type generation step so Node and Python contracts can't drift.
2. Add response caching for repeated questions.
3. Add a demo auth token for the public Netlify/Render combination.
4. Add Playwright or Vitest coverage for the Express proxy routes.
5. Extract the IXOR color tokens into a small shared CSS/SCSS variables file if more pages are added.
