import anthropic

from app.agents.copywriter.schemas import EmailDraft, QAScore
from app.tenants.models import Tenant

QA_TOOL = {
    "name": "evaluate_email",
    "description": "Evalúa la calidad del cold email generado",
    "input_schema": {
        "type": "object",
        "properties": {
            "personalization": {
                "type": "number",
                "description": (
                    "0-1. ¿La primera línea es específica al lead "
                    "(nombre, empresa, señal real)? 0=completamente genérico."
                ),
            },
            "spam_risk": {
                "type": "number",
                "description": (
                    "0-1. 0=sin riesgo. Penalizar: 'garantizado', 'gratis', "
                    "'oferta', 'URGENTE', exceso de signos de exclamación."
                ),
            },
            "tone_match": {
                "type": "number",
                "description": "0-1. ¿El tono coincide con las instrucciones de voz del tenant?",
            },
            "cta_clarity": {
                "type": "number",
                "description": "0-1. ¿Hay exactamente un CTA claro? 0=sin CTA o múltiples CTAs confusos.",
            },
            "issues": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Lista de problemas específicos. Vacía si no hay.",
            },
        },
        "required": ["personalization", "spam_risk", "tone_match", "cta_clarity", "issues"],
    },
}

APPROVAL_THRESHOLD = 0.70
RETRY_THRESHOLD = 0.50


class QAAgent:

    def __init__(self) -> None:
        self.claude = anthropic.Anthropic()

    async def evaluate(
        self,
        draft: EmailDraft,
        tenant: Tenant,
    ) -> QAScore:

        config = tenant.icp_config or {}
        voice = config.get("voice_guidelines", "Profesional pero cercano")

        system_prompt = (
            "Eres el QA Agent de Boids. Evalúas cold emails B2B con criterios estrictos.\n"
            "Tu evaluación determina si el email se envía, se reintenta, o escala a revisión humana.\n"
            "Sé estricto — un email mediocre es peor que no enviar nada.\n"
            "Usa el tool evaluate_email para entregar tu evaluación."
        )

        user_message = f"""Evalúa este cold email:

SUBJECT: {draft.subject}

BODY:
{draft.body}

NOTAS DE PERSONALIZACIÓN DEL COPYWRITER:
{draft.personalization_notes}

VOZ ESPERADA DEL TENANT:
{voice}

Evalúa con los 4 criterios del tool."""

        response = self.claude.messages.create(
            model="claude-haiku-4-5-20251001",  # Haiku — tarea estructurada
            max_tokens=400,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            tools=[QA_TOOL],
            tool_choice={"type": "tool", "name": "evaluate_email"},
        )

        tool_block = next(b for b in response.content if b.type == "tool_use")
        data = tool_block.input

        total = QAScore.compute_total(
            personalization=data["personalization"],
            spam_risk=data["spam_risk"],
            tone_match=data["tone_match"],
            cta_clarity=data["cta_clarity"],
        )

        return QAScore(
            **data,
            total=total,
            approved=total >= APPROVAL_THRESHOLD,
        )
