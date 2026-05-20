from pydantic import BaseModel, Field


class EmailDraft(BaseModel):
    subject: str = Field(..., max_length=120)
    body: str = Field(..., max_length=1500)
    personalization_notes: str = Field(
        ...,
        description="Para debugging: qué usó el agente para personalizar",
    )


class QAScore(BaseModel):
    personalization: float = Field(
        ..., ge=0, le=1,
        description="¿Hay algo específico del lead? 0=genérico, 1=muy personalizado",
    )
    spam_risk: float = Field(
        ..., ge=0, le=1,
        description="0=seguro, 1=alto riesgo de spam",
    )
    tone_match: float = Field(
        ..., ge=0, le=1,
        description="¿Coincide con el voice del tenant?",
    )
    cta_clarity: float = Field(
        ..., ge=0, le=1,
        description="¿Hay un CTA claro y único?",
    )
    total: float = Field(..., ge=0, le=1)
    issues: list[str] = Field(
        default=[],
        description="Lista de problemas encontrados — se pasa como feedback al retry",
    )
    approved: bool

    @classmethod
    def compute_total(
        cls,
        personalization: float,
        spam_risk: float,
        tone_match: float,
        cta_clarity: float,
    ) -> float:
        # spam_risk se invierte: 0 riesgo = 1 punto
        return round(
            (personalization + (1 - spam_risk) + tone_match + cta_clarity) / 4, 3
        )
