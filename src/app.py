from src.graph import run_agent

if __name__ == "__main__":
    question = "How can IXOR earn users' trust in agentic AI?"
    response = run_agent(question)
    print(response["generation"])
