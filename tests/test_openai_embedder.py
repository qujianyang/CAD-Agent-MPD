from types import SimpleNamespace
from unittest.mock import Mock

from nvidia_embedder import OpenAIEmbedder


def _embedding_response(vectors):
    return SimpleNamespace(
        data=[
            SimpleNamespace(index=index, embedding=vector)
            for index, vector in enumerate(vectors)
        ]
    )


def test_openai_embedder_uses_same_model_for_query_and_passages():
    client = Mock()
    client.embeddings.create.side_effect = [
        _embedding_response([[0.1, 0.2]]),
        _embedding_response([[0.3], [0.4]]),
    ]
    embedder = OpenAIEmbedder("test-key", model="text-embedding-3-small")
    embedder._client = client

    assert embedder.embed_text("shock\nisolation") == [0.1, 0.2]
    chunks = [{"content": "Catalog\ndata"}, {"content": "Shock method"}]
    assert [
        chunk["embedding"] for chunk in embedder.embed_chunks(chunks)
    ] == [[0.3], [0.4]]

    query_call, passage_call = client.embeddings.create.call_args_list
    assert query_call.kwargs == {
        "model": "text-embedding-3-small",
        "input": "shock isolation",
        "encoding_format": "float",
    }
    assert passage_call.kwargs == {
        "model": "text-embedding-3-small",
        "input": ["Catalog data", "Shock method"],
        "encoding_format": "float",
    }


def test_openai_embedder_rejects_missing_key():
    try:
        OpenAIEmbedder("")
    except ValueError as exc:
        assert "OPENAI_API_KEY" in str(exc)
    else:
        raise AssertionError("Expected a missing-key error.")
