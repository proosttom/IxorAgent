// Browser client for the IxorAgent demo UI. Compiled to public/app.js.

interface Telemetry {
  request_id?: string;
  retrieval_steps?: unknown[];
  relevance?: { is_relevant: boolean; question_terms: number };
  llm?: Record<string, unknown>;
}

interface AskResponseBody {
  answer: string;
  telemetry: Telemetry;
}

interface ErrorResponseBody {
  detail: string;
}

interface AskFormConfig {
  corpus: "ixor_papers" | "cv_job_fit";
  formId: string;
  inputId: string;
  submitId: string;
  statusId: string;
  answerCardId: string;
  answerId: string;
  telemetryPanelId: string;
  telemetryId: string;
}

function bindAskForm(config: AskFormConfig): void {
  const form = document.getElementById(config.formId) as HTMLFormElement;
  const input = document.getElementById(config.inputId) as HTMLInputElement;
  const submitBtn = document.getElementById(config.submitId) as HTMLButtonElement;
  const statusEl = document.getElementById(config.statusId) as HTMLDivElement;
  const answerCard = document.getElementById(config.answerCardId) as HTMLDivElement;
  const answerEl = document.getElementById(config.answerId) as HTMLDivElement;
  const telemetryPanel = document.getElementById(
    config.telemetryPanelId
  ) as HTMLDetailsElement;
  const telemetryEl = document.getElementById(config.telemetryId) as HTMLPreElement;

  // Chips live as a sibling of the form (both inside the same hero section),
  // not nested inside it, so scope the lookup to the shared parent.
  form.parentElement?.querySelectorAll<HTMLButtonElement>(".chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      input.value = btn.dataset.question ?? "";
      form.requestSubmit();
    });
  });

  form.addEventListener("submit", async (event: SubmitEvent) => {
    event.preventDefault();
    const question = input.value.trim();
    if (!question) return;

    submitBtn.disabled = true;
    statusEl.textContent = "Asking IxorAgent...";
    answerCard.style.display = "none";
    telemetryPanel.style.display = "none";

    try {
      // Same-origin call: the Node server proxies this to the Python API.
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, corpus: config.corpus }),
      });

      const data = (await response.json()) as AskResponseBody | ErrorResponseBody;
      if (!response.ok) {
        throw new Error((data as ErrorResponseBody).detail || `Request failed (${response.status})`);
      }

      const okData = data as AskResponseBody;
      answerEl.textContent = okData.answer;
      answerCard.style.display = "block";
      telemetryEl.textContent = JSON.stringify(okData.telemetry, null, 2);
      telemetryPanel.style.display = "block";
      statusEl.textContent = "";
    } catch (error) {
      statusEl.textContent = `Error: ${(error as Error).message}`;
    } finally {
      submitBtn.disabled = false;
    }
  });
}

bindAskForm({
  corpus: "ixor_papers",
  formId: "ask-form",
  inputId: "question",
  submitId: "submit-btn",
  statusId: "status",
  answerCardId: "answer-card",
  answerId: "answer",
  telemetryPanelId: "telemetry-panel",
  telemetryId: "telemetry",
});

bindAskForm({
  corpus: "cv_job_fit",
  formId: "ask-form-fit",
  inputId: "question-fit",
  submitId: "submit-btn-fit",
  statusId: "status-fit",
  answerCardId: "answer-card-fit",
  answerId: "answer-fit",
  telemetryPanelId: "telemetry-panel-fit",
  telemetryId: "telemetry-fit",
});
