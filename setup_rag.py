"""
Pipeline: Ingest MIL-STD PDF, create embeddings, build vector store.
Run once to prepare the RAG system.

Usage:
  python setup_rag.py                 # Use NVIDIA API (recommended)
  python setup_rag.py --local         # Use local embeddings (offline)
"""
import sys
import argparse
from pathlib import Path
from mil_std_chunker import DocumentChunker
from nvidia_embedder import NVIDIAEmbedder, JSONVectorStore


def setup_rag_pipeline(pdf_path: str, api_key: str, output_store: str = "mil_std_embeddings.json", use_local: bool = False):
    """
    Complete pipeline: ingest PDF -> chunk -> embed -> store.
    
    Args:
        pdf_path: Path to MIL-STD PDF
        api_key: NVIDIA API key
        output_store: Where to save the vector store JSON
        use_local: Use local embeddings instead of NVIDIA API
    """
    
    print("=" * 60)
    print("MIL-STD RAG PIPELINE SETUP")
    print(f"Mode: {'LOCAL EMBEDDINGS' if use_local else 'NVIDIA API'}")
    print("=" * 60)
    
    # Step 1: Chunk the document
    print("\n[1/3] Ingesting and chunking PDF...")
    chunker = DocumentChunker(chunk_size=500, overlap=100)
    doc_metadata = chunker.ingest_pdf(pdf_path)
    
    print(f"  ✓ Ingested: {doc_metadata['filename']}")
    print(f"  ✓ Pages: {doc_metadata['page_count']}")
    print(f"  ✓ Chunks: {doc_metadata['chunk_count']}")
    print(f"  ✓ Preview: {doc_metadata['raw_content'][:100]}...")
    
    # Step 2: Create embeddings via NVIDIA API or local
    print(f"\n[2/3] Generating embeddings ({'local' if use_local else 'NVIDIA API'})...")
    embedder = NVIDIAEmbedder(api_key, use_local=use_local)

    # Test API if not using local
    if not use_local:
        if not embedder.test_api_key():
            print("\n⚠ API test failed. Falling back to local embeddings...")
            use_local = True
            embedder.use_local = True  # sync state so embed_text uses local path
    
    if use_local:
        print("Initializing local embedding model...")
        embedder._init_local_model()
    
    embedded_chunks = embedder.embed_chunks(doc_metadata["chunks"])
    
    # Step 3: Save to vector store
    print("\n[3/3] Saving to vector store...")
    store = JSONVectorStore(output_store)
    
    # Clean metadata for storage
    metadata_for_store = {
        "filename": doc_metadata["filename"],
        "filepath": doc_metadata["filepath"],
        "title": doc_metadata["title"],
        "author": doc_metadata["author"],
        "page_count": doc_metadata["page_count"],
        "chunk_count": len(embedded_chunks)
    }
    
    store.save(metadata_for_store, embedded_chunks)
    
    print("\n" + "=" * 60)
    print(f"✓ RAG SETUP COMPLETE!")
    print(f"  Vector store: {output_store}")
    print(f"  Ready for queries!")
    print("=" * 60)
    
    return embedded_chunks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Setup RAG vector store from MIL-STD PDF")
    parser.add_argument("--local", action="store_true", help="Use local embeddings instead of NVIDIA API")
    args = parser.parse_args()
    
    # Configuration
    PDF_PATH = r"C:\Users\qujia\QuantumKeyDistribution\CAD-Agent-MPD\iso_select[1].pdf"
    API_KEY = "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"
    
    if not Path(PDF_PATH).exists():
        print(f"ERROR: PDF not found at {PDF_PATH}")
        sys.exit(1)
    
    # Run pipeline
    setup_rag_pipeline(PDF_PATH, API_KEY, use_local=args.local)

