CHUNK_SIZE = 400
CHUNK_OVERLAP = 50


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = text.strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
    current_chunk_words: list[str] = []

    for paragraph in paragraphs:
        words = paragraph.split()

        if len(current_chunk_words) + len(words) <= chunk_size:
            current_chunk_words.extend(words)
        else:
            if current_chunk_words:
                chunks.append(" ".join(current_chunk_words))
                current_chunk_words = current_chunk_words[-overlap:] if overlap else []

            if len(words) > chunk_size:
                for i in range(0, len(words), chunk_size - overlap):
                    chunk_words = words[i : i + chunk_size]
                    if chunk_words:
                        chunks.append(" ".join(chunk_words))
                current_chunk_words = []
            else:
                current_chunk_words = words

    if current_chunk_words:
        chunks.append(" ".join(current_chunk_words))

    return [c for c in chunks if len(c.split()) >= 20]
