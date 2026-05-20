from app.knowledge.service import KnowledgeService
from app.leads.models import Lead

_svc = KnowledgeService()


async def build_rag_context(tenant_id: str, lead: Lead) -> str:
    industry = ""
    if lead.research_ctx:
        ctx = lead.research_ctx
        if ctx.get("company_context", {}).get("description"):
            industry = ctx["company_context"]["description"][:100]

    query = f"{lead.title} {lead.company} {industry}".strip()

    chunks = await _svc.retrieve_context(
        tenant_id=tenant_id,
        query=query,
        top_k=3,
        score_threshold=0.68,
    )

    if not chunks:
        return ""

    formatted = [
        f"[{chunk['doc_type'].upper()} — {chunk['title']}]\n{chunk['text']}"
        for chunk in chunks
    ]

    return "\n\n---\n\n".join(formatted)
