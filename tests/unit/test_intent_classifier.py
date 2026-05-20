import pytest
from unittest.mock import MagicMock, patch

from app.agents.scheduler.intent_classifier import IntentClassifier


def make_claude_response(intent: str, confidence: float, key_phrase: str):
    mock = MagicMock()
    mock.content = [
        MagicMock(
            type="tool_use",
            input={"intent": intent, "confidence": confidence, "key_phrase": key_phrase},
        )
    ]
    return mock


@pytest.mark.asyncio
async def test_classifier_returns_positive_for_interested_reply():
    with patch("app.agents.scheduler.intent_classifier.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.return_value = make_claude_response(
            "positive", 0.95, "me parece interesante"
        )
        clf = IntentClassifier()
        result = await clf.classify("Hola, me parece interesante, ¿cuándo podemos hablar?")

    assert result["intent"] == "positive"
    assert result["confidence"] >= 0.9


@pytest.mark.asyncio
async def test_classifier_returns_auto_reply_for_ooo():
    with patch("app.agents.scheduler.intent_classifier.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.return_value = make_claude_response(
            "auto_reply", 0.99, "fuera de oficina"
        )
        clf = IntentClassifier()
        result = await clf.classify(
            "Estoy fuera de oficina hasta el 30 de mayo. Responderé a mi regreso."
        )

    assert result["intent"] == "auto_reply"


@pytest.mark.asyncio
async def test_classifier_returns_negative_for_unsubscribe():
    with patch("app.agents.scheduler.intent_classifier.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.return_value = make_claude_response(
            "negative", 0.98, "no me interesa"
        )
        clf = IntentClassifier()
        result = await clf.classify(
            "No gracias, no me interesa. Por favor no me contacten más."
        )

    assert result["intent"] == "negative"


@pytest.mark.asyncio
async def test_classifier_returns_question_for_ambiguous_reply():
    with patch("app.agents.scheduler.intent_classifier.anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.return_value = make_claude_response(
            "question", 0.80, "¿cuánto cuesta?"
        )
        clf = IntentClassifier()
        result = await clf.classify("¿Cuánto cuesta la plataforma?")

    assert result["intent"] == "question"
    assert "key_phrase" in result
