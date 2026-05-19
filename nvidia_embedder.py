"""
Robust NVIDIA embeddings with validation and fallback to local embeddings.
"""
import requests
import json
from pathlib import Path
from typing import List, Dict, Any
import time
import sys

# Suppress SSL warnings
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class NVIDIAEmbedder:
    def __init__(self, api_key: str, model: str = "nvidia/NV-Embed-QA", use_local: bool = False):
        """
        Initialize NVIDIA embeddings client.
        
        Args:
            api_key: NVIDIA API key
            model: Embedding model name
            use_local: Fall back to local embeddings if API fails
        """
        self.api_key = api_key
        self.model = model
        self.base_url = "https://integrate.api.nvidia.com/v1/embeddings"
        self.use_local = use_local
        self.local_model = None
        self.api_works = None

    def test_api_key(self) -> bool:
        """Test if API key is valid by making a test call."""
        print("Testing NVIDIA API connection...", end=" ", flush=True)
        
        try:
            payload = {
                "model": self.model,
                "input": "test",
                "encoding_format": "float"
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json"
            }
            
            response = requests.post(
                self.base_url, 
                json=payload, 
                headers=headers, 
                verify=False, 
                timeout=10
            )
            
            if response.status_code == 200:
                print("✓ API is working")
                self.api_works = True
                return True
            elif response.status_code == 401:
                print("✗ API key invalid (401 Unauthorized)")
                self.api_works = False
                return False
            elif response.status_code == 429:
                print("⚠ API rate limited (429). Will retry with backoff")
                self.api_works = True
                return True
            else:
                print(f"✗ API error ({response.status_code})")
                print(f"  Response: {response.text[:200]}")
                self.api_works = False
                return False
                
        except requests.exceptions.Timeout:
            print("✗ Connection timeout")
            self.api_works = False
            return False
        except Exception as e:
            print(f"✗ Connection failed: {str(e)[:100]}")
            self.api_works = False
            return False

    def _init_local_model(self):
        """Initialize local embedding model as fallback."""
        if self.local_model is not None:
            return
        
        try:
            from sentence_transformers import SentenceTransformer
            print("Loading local embedding model...", end=" ", flush=True)
            self.local_model = SentenceTransformer("all-MiniLM-L6-v2")
            print("✓ Loaded")
        except ImportError:
            print("\n[WARN] sentence-transformers not installed. Install with: pip install sentence-transformers")
            if not self.use_local:
                raise
            return None

    def embed_text_nvidia(self, text: str, retry_count: int = 3) -> List[float]:
        """
        Generate embedding via NVIDIA API with exponential backoff.
        
        Args:
            text: Text to embed
            retry_count: Number of retries
            
        Returns:
            Embedding vector
        """
        for attempt in range(retry_count):
            try:
                payload = {
                    "model": self.model,
                    "input": text,
                    "encoding_format": "float"
                }
                
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "application/json"
                }
                
                response = requests.post(
                    self.base_url,
                    json=payload,
                    headers=headers,
                    verify=False,
                    timeout=15
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if "data" in data and len(data["data"]) > 0:
                        return data["data"][0]["embedding"]
                    else:
                        raise RuntimeError("No embedding in response")
                
                elif response.status_code == 429:  # Rate limited
                    wait_time = (2 ** attempt) + 1  # Exponential backoff
                    if attempt < retry_count - 1:
                        time.sleep(wait_time)
                        continue
                    else:
                        raise RuntimeError(f"Rate limited after {retry_count} attempts")
                
                elif response.status_code == 401:
                    raise RuntimeError("Invalid API key (401)")
                
                else:
                    raise RuntimeError(f"API error {response.status_code}: {response.text[:100]}")
                    
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if attempt < retry_count - 1:
                    wait_time = (2 ** attempt) + 1
                    time.sleep(wait_time)
                    continue
                else:
                    raise RuntimeError(f"Connection failed after {retry_count} attempts: {str(e)[:100]}")
        
        raise RuntimeError("All retry attempts failed")

    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding (API or local).
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        if not text or not text.strip():
            return [0.0] * 384  # Empty text gets zero vector
        
        # Try API first if it works
        if self.api_works is not False:
            try:
                return self.embed_text_nvidia(text, retry_count=3)
            except Exception as e:
                if self.use_local:
                    return self.embed_text_local(text)
                else:
                    raise
        
        # Fallback to local
        if self.use_local:
            return self.embed_text_local(text)
        else:
            raise RuntimeError("No embedding method available")

    def embed_text_local(self, text: str) -> List[float]:
        """Generate embedding using local model."""
        if self.local_model is None:
            self._init_local_model()
        
        embedding = self.local_model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate embeddings for all chunks with detailed progress.
        
        Args:
            chunks: List of chunk dicts with 'content' key
            
        Returns:
            Chunks augmented with 'embedding' key
        """
        embedded_chunks = []
        total = len(chunks)
        failed_count = 0
        
        print(f"\nEmbedding {total} chunks...\n")
        
        for idx, chunk in enumerate(chunks, 1):
            # Progress indicator
            progress = (idx / total) * 100
            print(f"[{progress:5.1f}%] Chunk {idx}/{total}...", end="\r", flush=True)
            
            try:
                embedding = self.embed_text(chunk["content"])
                chunk["embedding"] = embedding
                embedded_chunks.append(chunk)
                
                # Adaptive delay based on progress
                if idx % 100 == 0:
                    time.sleep(0.5)  # Longer break every 100 chunks
                else:
                    time.sleep(0.05)
                    
            except Exception as e:
                failed_count += 1
                if failed_count <= 5:  # Show first 5 errors
                    print(f"\n  ✗ Chunk {idx}: {str(e)[:80]}")
                
                # Use zero vector as last resort
                chunk["embedding"] = [0.0] * 384
                embedded_chunks.append(chunk)
        
        print(f"\n✓ Embedded {len(embedded_chunks)}/{total} chunks")
        if failed_count > 0:
            print(f"⚠ {failed_count} chunks used fallback embeddings")
        
        return embedded_chunks


class JSONVectorStore:
    def __init__(self, store_path: str = "mil_std_embeddings.json"):
        """
        Initialize JSON-based vector store.
        
        Args:
            store_path: Path to JSON file storing embeddings
        """
        self.store_path = Path(store_path)

    def save(self, doc_metadata: Dict[str, Any], embedded_chunks: List[Dict[str, Any]]):
        """
        Save document and embeddings to JSON (filtering zero embeddings).
        
        Args:
            doc_metadata: Document info (title, author, etc.)
            embedded_chunks: Chunks with embeddings
        """
        # Filter out pure zero-embedding chunks to save space
        chunks_with_real_embeddings = [
            c for c in embedded_chunks 
            if c.get("embedding") and sum(abs(x) for x in c["embedding"]) > 0.001
        ]
        
        store_data = {
            "metadata": doc_metadata,
            "chunks": chunks_with_real_embeddings
        }
        
        with open(self.store_path, "w") as f:
            json.dump(store_data, f, indent=2)
        
        file_size = self.store_path.stat().st_size / (1024*1024)  # MB
        print(f"✓ Saved {len(chunks_with_real_embeddings)} valid embeddings to {self.store_path} ({file_size:.1f} MB)")

    def load(self) -> Dict[str, Any]:
        """Load vector store from JSON."""
        if not self.store_path.exists():
            raise FileNotFoundError(f"Vector store not found: {self.store_path}")
        
        with open(self.store_path, "r") as f:
            return json.load(f)

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        import math
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)

    def search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Find most similar chunks to query embedding.
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            
        Returns:
            Top-k similar chunks with similarity scores
        """
        store = self.load()
        chunks = store["chunks"]
        
        # Calculate similarities
        scored_chunks = []
        for chunk in chunks:
            if "embedding" in chunk:
                similarity = self.cosine_similarity(query_embedding, chunk["embedding"])
                scored_chunks.append({
                    "id": chunk["id"],
                    "content": chunk["content"],
                    "similarity": similarity
                })
        
        # Sort by similarity and return top-k
        scored_chunks.sort(key=lambda x: x["similarity"], reverse=True)
        return scored_chunks[:top_k]

