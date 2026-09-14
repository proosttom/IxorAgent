```markdown
# Implementation Plan: Corrective RAG (CRAG) Agent with LangGraph

**Objective:** Build a self-reflective RAG agent over IXOR's published thought leadership ("Impact Papers") using `langgraph` and `pytest`, demonstrating rapid framework adoption and production software engineering practices.

---

## 1. Architecture Overview

A stateful directed graph implementing the Corrective RAG (CRAG) pattern:


```

[Start]
│
▼
[Retrieve] ──► [Grade Documents]
│
┌───────────┴───────────┐
(Relevant)             (Irrelevant)
│                       │
▼                       ▼
[Generate]           [Rewrite Query] ──► (Loop to Retrieve, max 2 retries)
│                       │ (If max retries reached)
│                       ▼
│                 [Fallback / Refusal Node]
▼                       │
[End] ◄───────────────────┘

```

### State Definition (`GraphState`)
* `question: str` — Current user query or rewritten query.
* `original_question: str` — Preserved initial user input.
* `documents: list[Document]` — Chunks retrieved from the vector store.
* `retry_count: int` — Loop guard to prevent runaway execution (max 2).
* `generation: str` — Synthesized response or graceful fallback explanation.

---

## 2. Milestones & Timeline

| Day | Focus | Scope | Deliverable |
| :--- | :--- | :--- | :--- |
| **Tuesday Evening** (~1.5h) | Ingestion & Core Graph | Ingest IXOR sample text, configure in-memory FAISS/Chroma, build state nodes. | Working terminal script executing standard RAG path. |
| **Wednesday Evening** (~1.0h) | Conditional Edges & Routing | Implement grading node, rewrite logic, retry boundary guard. | Working cyclical agent recovering from irrelevant queries. |
| **Thursday Evening** (~1.0h) | Engineering Rigor & Polish | Write `pytest` unit tests with mocked state transitions, prep demo notes. | Clean Git repo with automated tests and crisp pitch narrative. |

---

## 3. Project Directory Structure

```text
ixor-crag-agent/
├── data/
│   └── ixor_impact_papers.txt    # Markdown/text excerpts of IXOR articles
├── src/
│   ├── __init__.py
│   ├── state.py                  # TypedDict GraphState definition
│   ├── vectorstore.py            # Local in-memory FAISS/Chroma setup
│   ├── nodes.py                  # retrieve, grade, generate, rewrite
│   ├── graph.py                  # LangGraph StateGraph assembly & compile
│   └── app.py                    # Lightweight CLI entrypoint
├── tests/
│   ├── __init__.py
│   └── test_graph_routing.py     # Deterministic pytest assertions on routing
├── requirements.txt
├── Dockerfile                    # Clean multi-stage build showcasing DevOps habit
└── README.md                     # Architecture diagram + run instructions

```

---

## 4. Step-by-Step Task Breakdown

### Step 1: Environment & Curated Knowledge Corpus (30 mins)

1. **Virtual Environment & Dependencies:**
```bash
pip install langgraph langchain-core langchain-openai faiss-cpu pytest pydantic

```


2. **Corpus Preparation (`data/ixor_impact_papers.txt`):**
* Paste key excerpts from IXOR's core publications:
* *“How to Earn Users’ Trust in Agentic AI”* (focus: predictability, transparency, human agency).
* *“Not Every Process Needs an Agent”* (focus: deterministic vs. non-deterministic trade-offs).
* Company positioning (*“Software, cloud en AI - gebouwd door engineers die je bedrijf kennen”*).





### Step 2: In-Memory Vector Store & Schema (30 mins)

1. Use `RecursiveCharacterTextSplitter` (chunk size ~400, overlap ~50).
2. Store in an in-memory `FAISS` index using `OpenAIEmbeddings(model="text-embedding-3-small")`.
3. Define strict Pydantic grading output:
```python
from pydantic import BaseModel, Field

class GradeDocuments(BaseModel):
    """Binary assessment of document relevance."""
    is_relevant: bool = Field(description="True if documents contain context to answer the question, False otherwise.")

```



### Step 3: Graph Nodes & Routing (60 mins)

1. **`retrieve(state: GraphState)`**: Fetches top 3 chunks for `state["question"]`.
2. **`grade_documents(state: GraphState)`**:
* Evaluates retrieved text against the question using structured output (`with_structured_output(GradeDocuments)`).


3. **`decide_to_generate(state: GraphState)`** (Conditional Edge):
* If `is_relevant is True` $\rightarrow$ Route to `generate`.
* If `is_relevant is False` and `retry_count < 2` $\rightarrow$ Route to `rewrite_query`.
* If `retry_count >= 2` $\rightarrow$ Route to `fallback` (graceful failure stating data is absent).


4. **`rewrite_query(state: GraphState)`**:
* Rewrites question to optimize semantic similarity; increments `retry_count += 1`.


5. **`generate(state: GraphState)`**:
* Answers question strictly from `state["documents"]`.



### Step 4: Engineering Rigor — Pytest Verification (45 mins)

*Mock the LLM/retrieval steps to verify graph mechanics deterministically without burning tokens or relying on external APIs:*

```python
# tests/test_graph_routing.py
def test_routing_to_rewrite_when_irrelevant(mock_state):
    """Assert graph correctly routes to query rewriting when documents fail relevance grade."""
    mock_state["documents"] = [Document(page_content="Unrelated text about gardening.")]
    result = decide_to_generate(mock_state)
    assert result == "rewrite_query"

def test_circuit_breaker_on_max_retries(mock_state):
    """Assert agent terminates gracefully instead of entering an infinite loop."""
    mock_state["retry_count"] = 2
    mock_state["documents"] = []
    result = decide_to_generate(mock_state)
    assert result == "fallback"

```

### Step 5: Containerize & README Documentation (30 mins)

1. Minimal `Dockerfile` showcasing production readiness:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["pytest"]

```


2. Short `README.md` highlighting:
* Architecture graph ASCII.
* How state cycles work and how hallucinations/loops are guarded against.



---

## 5. The Interview Pitch Strategy (For Friday)

During the call, frame this POC as proof of your core engineering philosophy:

1. **Acknowledge the Gap Directly:**
> *"I noticed the vacancy emphasizes LangGraph and agentic frameworks. While my background has been deeply rooted in ML infrastructure, test frameworks, and automotive systems, I spent a couple of evenings ramping up on LangGraph to explore its operational patterns."*


2. **Showcase the Differentiator (Control & Reliability):**
> *"Rather than building a standard conversational bot, I built a Corrective RAG pipeline over your own Impact Papers on agent trust. I focused specifically on non-deterministic failure modes: document relevance grading, self-correcting query rewrites, and strict circuit breakers to prevent infinite loops."*


3. **Connect to Your GoodiX / Testing Background:**
> *"Just like reforming test infrastructure at GoodiX, my priority here was testability: I wrote deterministic unit tests mocking graph state transitions so the agent's routing logic can be validated in a CI/CD pipeline."*



```

```