import pytest
from app.agents.research.schemas import ResearchContext, ResearchSignal, CompanyContext


def test_research_context_defaults_are_safe():
    ctx = ResearchContext(
        summary="Sin datos suficientes",
        limited_data=True,
        data_quality="low",
    )
    assert ctx.signals == []
    assert ctx.pain_points == []
    assert ctx.limited_data is True


def test_research_context_serializes_to_dict():
    ctx = ResearchContext(
        summary="Empresa en crecimiento",
        signals=[
            ResearchSignal(
                type="hiring",
                description="Contratando 3 ingenieros de datos",
                relevance="Señal de escala de infraestructura",
                date="2025-03",
            )
        ],
        data_quality="high",
    )
    d = ctx.model_dump()
    assert isinstance(d, dict)
    assert len(d["signals"]) == 1
    assert d["signals"][0]["type"] == "hiring"


def test_signal_types_are_validated():
    with pytest.raises(Exception):
        ResearchSignal(
            type="invalid_type",
            description="test",
            relevance="test",
        )


def test_research_context_max_signals():
    with pytest.raises(Exception):
        ResearchContext(
            summary="test",
            signals=[
                ResearchSignal(type="news", description=f"signal {i}", relevance="r")
                for i in range(6)
            ],
        )
