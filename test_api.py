"""
Test NVIDIA API connection before running full pipeline.
"""
from nvidia_embedder import NVIDIAEmbedder

# Your API key
API_KEY = "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"

print("=" * 60)
print("NVIDIA API DIAGNOSTIC TEST")
print("=" * 60)

embedder = NVIDIAEmbedder(API_KEY)
works = embedder.test_api_key()

if works:
    print("\n✓ API connection successful!")
    print("  You can run: python setup_rag.py")
else:
    print("\n✗ API connection failed!")
    print("  Options:")
    print("  1. Check your API key")
    print("  2. Check internet connection")
    print("  3. Use local embeddings: python setup_rag.py --local")
    print("  4. Install sentence-transformers: pip install sentence-transformers")
