from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentProfile:
    """Per-corpus configuration so nodes/llm stay corpus-agnostic."""

    corpus: str
    domain_terms: frozenset[str]
    domain_synonyms: dict[str, list[str]]
    rewrite_hints: tuple[str, str]  # generic hint for attempt 1 / attempt >=2
    llm_instruction: str
    fallback_message: str
    min_overlap_terms: int = 2
    # When true, any recognized domain term in the question is enough evidence
    # regardless of question length (used for narrow, single-topic corpora).
    broad_domain_match: bool = False
    # When true, a lexical rejection gets a second opinion from the LLM before
    # falling back, instead of relying solely on lexical overlap heuristics.
    use_llm_grading: bool = False


_IXOR_PAPERS = AgentProfile(
    corpus="ixor_papers",
    domain_terms=frozenset(
        {
            "accountability",
            "agent",
            "agentic",
            "autonomy",
            "deterministic",
            "predictability",
            "transparency",
            "trust",
        }
    ),
    domain_synonyms={
        "trust": ["transparency", "predictability", "respectful", "reliability"],
        "transparency": ["trust", "explain", "predictability"],
        "predictability": ["consistent", "trust", "reliability"],
        "autonomy": ["accountability", "boundaries", "oversight"],
        "accountability": ["autonomy", "oversight", "responsibility"],
        "agent": ["agentic", "automation", "deterministic"],
        "agentic": ["agent", "autonomous", "automation"],
        "deterministic": ["agent", "automation", "workflow"],
    },
    rewrite_hints=(
        "trust transparency predictability agentic AI",
        "autonomy accountability deterministic automation",
    ),
    llm_instruction=(
        "Answer only from these IXOR excerpts. Use 2-4 complete sentences, "
        "maximum 120 words. Cite source filenames in square brackets and "
        "do not invent facts."
    ),
    fallback_message=(
        "I couldn't find sufficient IXOR material to answer this confidently. "
        "Please rephrase the question or ask about trust, predictability, or "
        "agent suitability."
    ),
)

_CV_JOB_FIT = AgentProfile(
    corpus="cv_job_fit",
    domain_terms=frozenset(
        {
            "python",
            "typescript",
            "langgraph",
            "autogen",
            "agentic",
            "llm",
            "rag",
            "cloud",
            "aws",
            "azure",
            "fit",
            "gap",
            "experience",
            "caveat",
        }
    ),
    domain_synonyms={
        "fit": ["match", "experience", "skills", "qualifications"],
        "gap": ["caveat", "missing", "weakness"],
        "caveat": ["gap", "risk", "concern"],
        "agentic": ["agent", "langgraph", "autogen"],
        "cloud": ["aws", "azure"],
        "experience": ["background", "skills", "projects"],
    },
    rewrite_hints=(
        "job requirements skills experience responsibilities",
        "candidate background caveats gaps qualifications",
    ),
    llm_instruction=(
        "Answer only from these excerpts comparing a candidate CV against a job "
        "posting. Use 2-4 complete sentences, maximum 120 words. Point out "
        "concrete matches and concrete gaps or caveats. Do not invent facts."
    ),
    fallback_message=(
        "I couldn't find sufficient CV or job posting material to answer this "
        "confidently. Please rephrase the question or ask about fit, required "
        "skills, or caveats."
    ),
    # Narrow two-document corpus: synthesis questions ("fit", "caveats") rarely
    # share literal wording with the source text, so a single overlapping term
    # is enough evidence, unlike the broader multi-paper IXOR corpus.
    min_overlap_terms=1,
    broad_domain_match=True,
    use_llm_grading=True,
)

PROFILES: dict[str, AgentProfile] = {
    _IXOR_PAPERS.corpus: _IXOR_PAPERS,
    _CV_JOB_FIT.corpus: _CV_JOB_FIT,
}


def get_profile(corpus: str) -> AgentProfile:
    return PROFILES.get(corpus, _IXOR_PAPERS)
