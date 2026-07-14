from unittest.mock import Mock, patch

from nvidia_embedder import OllamaEmbedder


def _response(embeddings):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"embeddings": embeddings}
    response.text = ""
    return response


def test_mxbai_prefix_applies_to_queries_not_passages():
    embedder = OllamaEmbedder("hf.co/mixedbread-ai/mxbai-embed-large-v1:F16")
    with patch("nvidia_embedder.requests.post", return_value=_response([[0.1, 0.2]])) as post:
        assert embedder.embed_text("Which catalog has the softest mount?") == [0.1, 0.2]

    assert post.call_args.kwargs["json"]["input"] == (
        "Represent this sentence for searching relevant passages: "
        "Which catalog has the softest mount?"
    )


def test_bge_passages_are_embedded_without_query_instruction():
    chunks = [{"content": "Catalog data"}, {"content": "Shock method"}]
    embedder = OllamaEmbedder("bge-m3")
    with patch("nvidia_embedder.requests.post", return_value=_response([[0.1], [0.2]])) as post:
        embedded = embedder.embed_chunks(chunks)

    assert post.call_args.kwargs["json"]["input"] == ["Catalog data", "Shock method"]
    assert [chunk["embedding"] for chunk in embedded] == [[0.1], [0.2]]
