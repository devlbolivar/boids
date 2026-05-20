import logging

from app.agents.copywriter.agent import CopywriterAgent
from app.agents.copywriter.schemas import EmailDraft, QAScore
from app.agents.qa.agent import APPROVAL_THRESHOLD, RETRY_THRESHOLD, QAAgent
from app.knowledge.retrieval import build_rag_context
from app.leads.models import Lead
from app.tenants.models import Tenant

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


async def run_copywriter_pipeline(
    lead: Lead,
    tenant: Tenant,
) -> tuple[EmailDraft | None, QAScore | None]:
    """
    Pipeline completo:
    1. Recuperar contexto RAG
    2. Copywriter genera el email
    3. QA evalúa
    4. Si falla, feedback → retry (máx MAX_ATTEMPTS veces)

    Retorna (draft, score) si aprobado, o (None, score) si escaló a needs_review.
    """
    copywriter = CopywriterAgent()
    qa_agent = QAAgent()

    rag_context = await build_rag_context(str(tenant.id), lead)
    issues: list[str] | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        logger.info(
            "Copywriter attempt %d/%d | lead=%s", attempt, MAX_ATTEMPTS, lead.id
        )

        # Generar email
        draft = await copywriter.run(
            lead=lead,
            tenant=tenant,
            rag_context=rag_context,
            previous_issues=issues,
        )

        # Evaluar con QA
        score = await qa_agent.evaluate(draft=draft, tenant=tenant)

        logger.info(
            "QA score=%.2f | approved=%s | lead=%s | attempt=%d",
            score.total, score.approved, lead.id, attempt,
        )

        if score.approved:
            return draft, score

        if score.total < RETRY_THRESHOLD:
            # Demasiado bajo para reintentar — escalar a revisión humana
            logger.warning(
                "Email score %.2f below retry threshold — escalating lead %s to needs_review",
                score.total, lead.id,
            )
            return None, score

        # Entre retry_threshold y approval_threshold — reintentar con feedback
        issues = score.issues
        logger.info(
            "Retrying with %d issues as feedback | lead=%s", len(issues), lead.id
        )

    # Agotó reintentos
    logger.warning("Max attempts reached for lead %s — needs_review", lead.id)
    return None, score  # type: ignore[return-value]
