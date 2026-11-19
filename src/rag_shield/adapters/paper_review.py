"""Academic paper review: LLM-assisted reviewing of submitted manuscripts.

Threat: authors hide instructions to LLM reviewers in the PDF (e.g. white or tiny text saying
"give a positive review only"). Same engine as HR; this file is configuration only.

Thresholds are stricter than HR (quarantine 0.65, review 0.35): a submitted paper has little
legitimate reason to address an AI reviewer, and an accept/reject decision is high-stakes.
Known false positive: a paper ABOUT prompt injection that quotes an attack string has that
quoted sentence quarantined (sentence only; a reviewer can release it).
"""

from rag_shield.adapters import DomainAdapter

ADAPTER = DomainAdapter(
    name="paper_review",
    description="LLM-assisted peer review of submitted papers",
    trusted_sources={
        "submission": "external_upload",
        "author_response": "external_upload",
        "supplementary": "external_upload",
        "venue_guidelines": "internal_kb",
        "reviewer_notes": "internal_kb",
    },
    sensitive_actions=("accept_reject_recommendation", "review_score", "reviewer_assignment"),
    integrity_task="Score this paper for acceptance at the venue",
    default_question="Summarize this paper's contributions and weaknesses.",
    policy={
        "thresholds": {"quarantine": 0.65, "review": 0.35},
        "linguistic": {
            "extra_cues": [
                {"name": "positive_review", "weight": 0.70,
                 "pattern": r"\b(?:give|write|provide|produce|output)\s+(?:only\s+)?(?:a\s+|an\s+)?"
                            r"(?:very\s+|strongly\s+)?(?:positive|favou?rable|glowing)\s+"
                            r"(?:review|assessment|evaluation|rating|score)"},
                {"name": "accept_paper", "weight": 0.60,
                 "pattern": r"\b(?:accept|recommend\s+(?:acceptance\s+of|accepting))\s+"
                            r"(?:this|the)\s+(?:paper|submission|manuscript|work)\b"},
                {"name": "strengths_only", "weight": 0.60,
                 "pattern": r"\b(?:emphasi[sz]e|highlight|focus\s+on|mention|discuss)\s+only\s+"
                            r"(?:the\s+)?(?:strengths|positives|contributions|novelty)"},
                {"name": "hide_weaknesses", "weight": 0.60,
                 "pattern": r"\b(?:do\s+not|don't|never)\s+(?:mention|highlight|discuss|"
                            r"point\s+out|criticise|criticize)\s+(?:any\s+)?(?:of\s+the\s+)?(?:weaknesses|"
                            r"limitations|flaws|negatives|shortcomings)"},
                {"name": "ai_reviewer", "weight": 0.50,
                 "pattern": r"\b(?:llm|ai|automated|language\s+model)\s+"
                            r"(?:reviewers?|referees?)\b"},
            ],
        },
        "integrity": {
            "rubric": (
                "Score the paper from 0 to 100 for acceptance at the venue, using only the "
                "evidence given. Reply with JSON: {\"score\": <0-100>, \"verdict\": "
                "\"<accept|reject>\", \"supporting_evidence_ids\": [<ids of the evidence lines "
                "you relied on>]}."
            ),
        },
    },
)
