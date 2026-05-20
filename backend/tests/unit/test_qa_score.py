from app.agents.copywriter.schemas import QAScore


def test_compute_total_perfect_score():
    total = QAScore.compute_total(
        personalization=1.0,
        spam_risk=0.0,
        tone_match=1.0,
        cta_clarity=1.0,
    )
    assert total == 1.0


def test_compute_total_spam_risk_is_inverted():
    # Alto spam_risk baja el score
    total_low_risk = QAScore.compute_total(1.0, 0.0, 1.0, 1.0)
    total_high_risk = QAScore.compute_total(1.0, 1.0, 1.0, 1.0)
    assert total_low_risk > total_high_risk


def test_approval_threshold():
    score = QAScore(
        personalization=0.8,
        spam_risk=0.1,
        tone_match=0.8,
        cta_clarity=0.9,
        total=0.85,
        issues=[],
        approved=True,
    )
    assert score.approved is True
    assert score.total >= 0.70


def test_below_threshold_not_approved():
    score = QAScore(
        personalization=0.3,
        spam_risk=0.5,
        tone_match=0.4,
        cta_clarity=0.3,
        total=0.375,
        issues=["Email muy genérico", "Alto riesgo de spam"],
        approved=False,
    )
    assert score.approved is False
