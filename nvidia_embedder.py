"""
NVIDIA embeddings via LangChain with local fallback.
"""
import json
import math
import time
from pathlib import Path
from typing import List, Dict, Any

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class NVIDIAEmbedder:
    def __init__(self, api_key: str, model: str = "nvidia/llama-nemotron-embed-1b-v2", use_local: bool = False):
        self.api_key = api_key
        self.model = model
        self.use_local = use_local
        self.local_model = None
        self.api_works = None
        self._client = None

    def _get_client(self):
        if self._client is None:
            from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
            self._client = NVIDIAEmbeddings(
                model=self.model,
                api_key=self.api_key,
                truncate="NONE",
            )
        return self._client

    def test_api_key(self) -> bool:
        print("Testing NVIDIA API connection...", end=" ", flush=True)
        try:
            self._get_client().embed_query("test")
            print("[OK] API is working")
            self.api_works = True
            return True
        except Exception as e:
            msg = str(e)[:80]
            if "401" in msg:
                print(f"[FAIL] API key invalid (401)")
            elif "429" in msg:
                print("[WARN] Rate limited (429)")
                self.api_works = True
                return True
            else:
                print(f"[FAIL] {msg}")
            self.api_works = False
            return False

    def _init_local_model(self):
        if self.local_model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
            print("Loading local embedding model...", end=" ", flush=True)
            self.local_model = SentenceTransformer("all-MiniLM-L6-v2")
            print("[OK] Loaded")
        except ImportError:
            print("\n[WARN] Install with: pip install sentence-transformers")
            raise

    def embed_text(self, text: str) -> List[float]:
        if not text or not text.strip():
            return [0.0] * 384

        if not self.use_local and self.api_works is not False:
            try:
                return self._get_client().embed_query(text)
            except Exception as e:
                if self.use_local:
                    return self.embed_text_local(text)
                raise

        if self.use_local:
            return self.embed_text_local(text)

        raise RuntimeError("No embedding method available")

    def embed_text_local(self, text: str) -> List[float]:
        if self.local_model is None:
            self._init_local_model()
        return self.local_model.encode(text, convert_to_numpy=True).tolist()

    def embed_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        total = len(chunks)
        failed_count = 0
        print(f"\nEmbedding {total} chunks...\n")

        # Batch embed via NVIDIA API (uses input_type="passage" internally)
        if not self.use_local and self.api_works is not False:
            try:
                texts = [c["content"] for c in chunks]
                print("Batch embedding via NVIDIA API...")
                embeddings = self._get_client().embed_documents(texts)
                for chunk, emb in zip(chunks, embeddings):
                    chunk["embedding"] = emb
                print(f"[OK] Embedded {total}/{total} chunks")
                return chunks
            except Exception as e:
                print(f"Batch embed failed ({str(e)[:80]}), falling back to per-chunk...")

        # Per-chunk fallback
        embedded = []
        for idx, chunk in enumerate(chunks, 1):
            print(f"[{idx/total*100:5.1f}%] Chunk {idx}/{total}...", end="\r", flush=True)
            try:
                chunk["embedding"] = self.embed_text(chunk["content"])
                embedded.append(chunk)
                time.sleep(0.05)
            except Exception as e:
                failed_count += 1
                if failed_count <= 5:
                    print(f"\n  [FAIL] Chunk {idx}: {str(e)[:80]}")
                chunk["embedding"] = [0.0] * 384
                embedded.append(chunk)

        print(f"\n[OK] Embedded {len(embedded)}/{total} chunks")
        if failed_count:
            print(f"[WARN] {failed_count} chunks used fallback embeddings")
        return embedded


class JSONVectorStore:
    def __init__(self, store_path: str = "artifacts/mil_std_embeddings.json"):
        self.store_path = Path(store_path)

    def save(self, doc_metadata: Dict[str, Any], embedded_chunks: List[Dict[str, Any]]):
        valid = [c for c in embedded_chunks if c.get("embedding") and sum(abs(x) for x in c["embedding"]) > 0.001]
        store_data = {"metadata": doc_metadata, "chunks": valid}
        with open(self.store_path, "w") as f:
            json.dump(store_data, f, indent=2)
        size_mb = self.store_path.stat().st_size / (1024 * 1024)
        print(f"[OK] Saved {len(valid)} valid embeddings to {self.store_path} ({size_mb:.1f} MB)")

    def load(self) -> Dict[str, Any]:
        if not self.store_path.exists():
            raise FileNotFoundError(f"Vector store not found: {self.store_path}")
        with open(self.store_path) as f:
            return json.load(f)

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        dot = sum(a * b for a, b in zip(vec1, vec2))
        n1 = math.sqrt(sum(a * a for a in vec1))
        n2 = math.sqrt(sum(b * b for b in vec2))
        if n1 == 0 or n2 == 0:
            return 0.0
        return dot / (n1 * n2)

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        parent_topic: str | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Cosine-similarity search over the stored chunks.

        Args:
            query_embedding: Embedded query vector.
            top_k:           Number of results to return.
            parent_topic:    Optional — restrict search to chunks whose
                             `parent_topic` matches (e.g. "shock_mount").
                             Set to None to search across all topics.

        Returns each hit with: id, content, similarity, plus any chunk
        metadata (parent_topic, child_name, title, source_path) if present.
        """
        chunks = self.load()["chunks"]
        if parent_topic:
            chunks = [c for c in chunks if c.get("parent_topic") == parent_topic]

        scored = []
        for c in chunks:
            if "embedding" not in c:
                continue
            hit = {
                "id":           c.get("id"),
                "content":      c.get("content", ""),
                "similarity":   self.cosine_similarity(query_embedding, c["embedding"]),
                "parent_topic": c.get("parent_topic"),
                "child_name":   c.get("child_name"),
                "title":        c.get("title"),
                "source_path":  c.get("source_path"),
            }
            scored.append(hit)
        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:top_k]
