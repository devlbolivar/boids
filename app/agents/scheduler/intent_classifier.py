import anthropic
from typing import Literal

IntentType = Literal["positive", "negative", "question", "auto_reply"]

INTENT_TOOL = {
    "name": "classify_intent",
    "description": "Clasifica la intención del reply al cold email",
    "input_schema": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "enum": ["positive", "negative", "question", "auto_reply"],
                "description": (
                    "positive: interesado, quiere reunirse, pide más info con intención de avanzar. "
                    "negative: no interesado, pide que no le escriban más, unsubscribe. "
                    "question: pregunta sobre el producto sin compromiso claro. "
                    "auto_reply: respuesta automática de vacaciones o fuera de oficina."
                ),
            },
            "confidence": {
                "type": "number",
                "description": "0-1. Certeza de la clasificación.",
            },
            "key_phrase": {
                "type": "string",
                "description": "Frase del reply que justifica la clasificación.",
            },
        },
        "required": ["intent", "confidence", "key_phrase"],
    },
}


class IntentClassifier:

    def __init__(self):
        self.claude = anthropic.Anthropic()

    async def classify(self, reply_body: str) -> dict:
        """
        Clasifica la intención de un reply.
        Usa Haiku — tarea estructurada, no requiere razonamiento profundo.
        """
        response = self.claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            system="""Clasificas la intención de replies a cold emails B2B.
Sé conservador: clasifica como 'positive' solo si hay señal clara de interés.
Una pregunta sin compromiso es 'question', no 'positive'.
Usa el tool classify_intent para entregar tu clasificación.""",
            messages=[
                {
                    "role": "user",
                    "content": f"Clasifica este reply:\n\n{reply_body[:1000]}",
                }
            ],
            tools=[INTENT_TOOL],
            tool_choice={"type": "tool", "name": "classify_intent"},
        )

        block = next(b for b in response.content if b.type == "tool_use")
        return block.input  # type: ignore[return-value]
