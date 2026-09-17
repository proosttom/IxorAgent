// Express server: serves the IXOR-styled static frontend and proxies
// question requests to the Python IxorAgent API so the browser never
// needs to know the backend URL or handle its CORS policy directly.
import path from "path";
import dotenv from "dotenv";

dotenv.config({ path: path.join(__dirname, "..", ".env") });

import express, { type Request, type Response } from "express";
import cors from "cors";
import rateLimit from "express-rate-limit";
import type {
  AskRequestBody,
  AskResponseBody,
  ErrorResponseBody,
  HealthResponseBody,
} from "./types";

const IXOR_API_URL = process.env.IXOR_API_URL || "http://localhost:8000";
const MAX_QUESTION_LENGTH = 1_000;

const app = express();

app.use(cors());
app.use(express.json({ limit: "10kb" }));
app.use(express.static(path.join(__dirname, "..", "public")));

const askLimiter = rateLimit({
  windowMs: 60_000,
  limit: 20,
  standardHeaders: true,
  legacyHeaders: false,
  message: {
    detail: "Too many requests. Please wait a moment and try again.",
  } satisfies ErrorResponseBody,
});

app.get(
  "/api/health",
  async (_req: Request, res: Response<HealthResponseBody>) => {
    try {
      const upstream = await fetch(`${IXOR_API_URL}/health`);
      const body = (await upstream.json()) as HealthResponseBody;
      res.status(upstream.status).json(body);
    } catch {
      res.status(503).json({ status: "unreachable", service: "ixor-agent" });
    }
  }
);

app.post(
  "/api/ask",
  askLimiter,
  async (
    req: Request<{}, AskResponseBody | ErrorResponseBody, Partial<AskRequestBody>>,
    res: Response<AskResponseBody | ErrorResponseBody>
  ) => {
    const question =
      typeof req.body?.question === "string" ? req.body.question.trim() : "";
    const corpus =
      req.body?.corpus === "cv_job_fit" ? "cv_job_fit" : "ixor_papers";

    if (!question) {
      res.status(400).json({ detail: "Question must not be empty." });
      return;
    }
    if (question.length > MAX_QUESTION_LENGTH) {
      res.status(413).json({ detail: "Question is too long." });
      return;
    }

    try {
      const upstream = await fetch(`${IXOR_API_URL}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, corpus, verbose: true }),
      });
      const body = (await upstream.json()) as AskResponseBody | ErrorResponseBody;
      res.status(upstream.status).json(body);
    } catch {
      res
        .status(502)
        .json({ detail: "The IxorAgent API is currently unreachable." });
    }
  }
);

if (require.main === module) {
  const port = Number(process.env.PORT) || 3000;
  app.listen(port, () => {
    console.log(`IxorAgent web server listening on port ${port}`);
    console.log(`Proxying /api/* to ${IXOR_API_URL}`);
  });
}

export default app;
