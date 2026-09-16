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

const form = document.getElementById("ask-form") as HTMLFormElement;
const input = document.getElementById("question") as HTMLInputElement;
const submitBtn = document.getElementById("submit-btn") as HTMLButtonElement;
const statusEl = document.getElementById("status") as HTMLDivElement;
const answerCard = document.getElementById("answer-card") as HTMLDivElement;
const answerEl = document.getElementById("answer") as HTMLDivElement;
const telemetryPanel = document.getElementById(
  "telemetry-panel"
) as HTMLDetailsElement;
const telemetryEl = document.getElementById("telemetry") as HTMLPreElement;

document.querySelectorAll<HTMLButtonElement>(".chip").forEach((btn) => {
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
      body: JSON.stringify({ question }),
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
