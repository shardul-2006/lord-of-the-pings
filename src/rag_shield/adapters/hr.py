"""HR resume screening: the domain policy_v1 was written for, so no policy overrides."""

from rag_shield.adapters import DomainAdapter

ADAPTER = DomainAdapter(
    name="hr",
    description="Resume screening for hiring decisions",
    trusted_sources={
        "resume_upload": "external_upload",
        "cover_letter": "external_upload",
        "job_description": "internal_kb",
        "hr_policy_wiki": "internal_kb",
    },
    sensitive_actions=("shortlist", "reject", "rank_candidates"),
    integrity_task="Score this candidate for a software engineer role",
    default_question="Evaluate this candidate for a software engineer role.",
)
