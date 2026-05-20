from app.knowledge.chunker import chunk_text


def test_empty_text_returns_empty_list():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_short_text_below_minimum_filtered():
    result = chunk_text("Hola mundo esto es corto")
    assert result == []


def test_normal_text_produces_chunks():
    text = " ".join(["palabra"] * 600)
    chunks = chunk_text(text, chunk_size=400, overlap=50)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert len(chunk.split()) <= 410


def test_overlap_creates_continuity():
    words = [f"word{i}" for i in range(100)]
    text = " ".join(words)
    chunks = chunk_text(text, chunk_size=60, overlap=20)
    if len(chunks) >= 2:
        last_of_first = set(chunks[0].split()[-20:])
        first_of_second = set(chunks[1].split()[:20])
        assert len(last_of_first & first_of_second) > 0


def test_paragraph_boundaries_respected():
    # Both paragraphs fit in one chunk (combined > 20 words, < chunk_size)
    p1 = "Párrafo uno con bastante contenido relevante para verificar el comportamiento."
    p2 = "Párrafo dos también largo y con suficientes palabras para superar el mínimo requerido."
    text = f"{p1}\n\n{p2}"
    chunks = chunk_text(text, chunk_size=400)
    assert len(chunks) == 1
