// Shared contract types between the Node proxy and the Python IxorAgent API.

export interface AskRequestBody {
  question: string;
  corpus?: "ixor_papers" | "cv_job_fit";
}

export interface RetrievalHit {
  source: string;
  chunk_id: number;
  score: number;
}

export interface RetrievalStep {
  query: string;
  hits: RetrievalHit[];
}

export interface RelevanceTelemetry {
  is_relevant: boolean;
  question_terms: number;
}

export interface LlmTelemetry {
  provider?: string;
  model?: string | null;
  context_chars?: number;
  prompt_tokens?: number | null;
  output_tokens?: number | null;
  total_tokens?: number | null;
  finish_reason?: string;
}

export interface Telemetry {
  request_id?: string;
  retrieval_steps?: RetrievalStep[];
  relevance?: RelevanceTelemetry;
  llm?: LlmTelemetry;
}

export interface AskResponseBody {
  answer: string;
  telemetry: Telemetry;
}

export interface ErrorResponseBody {
  detail: string;
}

export interface HealthResponseBody {
  status: string;
  service: string;
}
