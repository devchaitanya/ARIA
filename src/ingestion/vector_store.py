def build_context_chunks(files: list[dict], max_chunk_chars: int = 6000) -> list[dict]:
    """Split files into chunks suitable for LLM context windows."""
    chunks = []
    for f in files:
        content = f["content"]
        path = f["path"]
        if len(content) <= max_chunk_chars:
            chunks.append({"path": path, "chunk_id": 0, "content": content})
        else:
            lines = content.split("\n")
            current_chunk = []
            current_len = 0
            chunk_id = 0
            for line in lines:
                if current_len + len(line) > max_chunk_chars and current_chunk:
                    chunks.append({
                        "path": path,
                        "chunk_id": chunk_id,
                        "content": "\n".join(current_chunk),
                    })
                    chunk_id += 1
                    current_chunk = []
                    current_len = 0
                current_chunk.append(line)
                current_len += len(line) + 1
            if current_chunk:
                chunks.append({
                    "path": path,
                    "chunk_id": chunk_id,
                    "content": "\n".join(current_chunk),
                })
    return chunks
