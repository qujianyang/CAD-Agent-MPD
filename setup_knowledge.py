"""
Ingest the hierarchical knowledge/ folder into a JSON vector store.

Layout:
  knowledge/
    shock_mount/
      formulas.md         <- one chunk
      load_cases.md       <- one chunk
      selection_rules.md  <- one chunk
      catalog_overview.md <- one chunk
    generator/   (future)
    thermal/     (future)

Each .md file becomes ONE chunk (no sentence splitting — files are intentionally
small enough). Metadata stored per chunk:
  - parent_topic : folder name        (e.g. "shock_mount")
  - child_name   : filename stem      (e.g. "formulas")
  - title        : first H1 in file   (e.g. "Shock Isolation Formulas...")
  - source_path  : relative file path
  - content      : full markdown body
  - id           : "parent_topic/child_name"

Usage:
  python setup_knowledge.py                # build the normal mixed development index
  python setup_knowledge.py --local        # use local SentenceTransformer fallback
  python setup_knowledge.py --provider ollama --model bge-m3
  python setup_knowledge.py --provider openai --model text-embedding-3-small
  python setup_knowledge.py --topic shock_mount --output artifacts/shock_mount_embeddings.json
                                            # build a shock-only index
"""
import argparse
import os
import re
import sys
from pathlib import Path
from dotenv import load_dotenv

from nvidia_embedder import (
    JSONVectorStore,
    NVIDIAEmbedder,
    OllamaEmbedder,
    OpenAIEmbedder,
)


# Where the source markdown lives, and where the vector store goes
KNOWLEDGE_DIR  = Path(__file__).parent / "knowledge"
STORE_PATH     = Path(__file__).parent / "artifacts" / "knowledge_embeddings.json"


def _extract_title(md_text: str, fallback: str) -> str:
    """Pull the first H1 (# Title) from the markdown; fall back to filename."""
    for line in md_text.splitlines():
        m = re.match(r"^\s*#\s+(.+?)\s*$", line)
        if m:
            return m.group(1).strip()
    return fallback


def collect_chunks(knowledge_dir: Path, topic: str | None = None) -> list[dict]:
    """Walk knowledge/ and build one chunk per .md file, optionally by topic."""
    if not knowledge_dir.exists():
        print(f"ERROR: {knowledge_dir} does not exist.")
        sys.exit(1)

    chunks: list[dict] = []
    for md_path in sorted(knowledge_dir.rglob("*.md")):
        # knowledge/shock_mount/formulas.md
        #          ^parent      ^child
        rel = md_path.relative_to(knowledge_dir)
        parts = rel.parts
        if len(parts) < 2:
            print(f"  [skip] {rel} — must live inside a parent topic folder")
            continue

        parent_topic = parts[0]
        if topic and parent_topic != topic:
            continue
        child_name   = md_path.stem
        content      = md_path.read_text(encoding="utf-8")
        title        = _extract_title(content, fallback=child_name.replace("_", " ").title())

        chunks.append({
            "id":           f"{parent_topic}/{child_name}",
            "parent_topic": parent_topic,
            "child_name":   child_name,
            "title":        title,
            "source_path":  str(rel).replace("\\", "/"),
            "content":      content,
        })
        print(f"  + {parent_topic}/{child_name}  ({len(content)} chars)  {title!r}")
    return chunks


def main(
    use_local: bool = False,
    topic: str | None = None,
    output_path: Path = STORE_PATH,
    provider: str = "nvidia",
    model: str | None = None,
    base_url: str = "http://127.0.0.1:11434",
    query_prefix: str | None = None,
):
    load_dotenv()
    nvidia_api_key = os.environ.get("NVIDIA_API_KEY", "")
    openai_api_key = os.environ.get("OPENAI_API_KEY", "")
    if use_local:
        provider = "sentence_transformers"
    if provider == "nvidia" and not nvidia_api_key:
        print("ERROR: NVIDIA_API_KEY not set. Run with --local or add it to .env.")
        sys.exit(1)
    if provider == "openai" and not openai_api_key:
        print("ERROR: OPENAI_API_KEY not set. Add it to .env.")
        sys.exit(1)
    if provider not in {"nvidia", "openai", "ollama", "sentence_transformers"}:
        print(f"ERROR: unsupported embedding provider {provider!r}.")
        sys.exit(1)

    print("=" * 60)
    print("KNOWLEDGE BASE EMBEDDING PIPELINE")
    print(f"Provider: {provider}")
    print(f"Model: {model or ('local' if provider == 'sentence_transformers' else 'nvidia/llama-nemotron-embed-1b-v2')}")
    print(f"Source: {KNOWLEDGE_DIR}")
    print(f"Topic filter: {topic or 'all topics'}")
    print(f"Output: {output_path}")
    print("=" * 60)

    # 1. Collect chunks from the folder tree
    print("\n[1/3] Walking knowledge/ folder...")
    chunks = collect_chunks(KNOWLEDGE_DIR, topic=topic)
    if not chunks:
        print("No markdown files found. Aborting.")
        sys.exit(1)

    # Group summary by parent topic
    by_parent: dict[str, list[str]] = {}
    for c in chunks:
        by_parent.setdefault(c["parent_topic"], []).append(c["child_name"])
    print(f"\n  Topics discovered:")
    for parent, children in by_parent.items():
        print(f"    {parent}/  ->  {', '.join(children)}")

    # 2. Embed
    print(f"\n[2/3] Embedding {len(chunks)} chunks...")
    if provider == "ollama":
        if not model:
            print("ERROR: --model is required with --provider ollama.")
            sys.exit(1)
        embedder = OllamaEmbedder(model=model, base_url=base_url, query_prefix=query_prefix)
        embedding_model = model
    elif provider == "openai":
        embedding_model = model or "text-embedding-3-small"
        embedder = OpenAIEmbedder(
            api_key=openai_api_key,
            model=embedding_model,
        )
    else:
        use_local = provider == "sentence_transformers"
        embedder = NVIDIAEmbedder(
            nvidia_api_key,
            model=model or "nvidia/llama-nemotron-embed-1b-v2",
            use_local=use_local,
        )
        embedding_model = "local" if use_local else embedder.model
    if provider == "nvidia":
        if not embedder.test_api_key():
            print("\n  API failed -> falling back to local embeddings.")
            embedder.use_local = True
            use_local = True
            provider = "sentence_transformers"
            embedding_model = "local"
    if provider == "sentence_transformers":
        embedder._init_local_model()

    embedded = embedder.embed_chunks(chunks)

    # 3. Save
    print("\n[3/3] Saving vector store...")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    store = JSONVectorStore(str(output_path))
    metadata = {
        "source":     "knowledge/",
        "topic_filter": topic,
        "topics":     by_parent,
        "chunk_count": len(embedded),
        "embedding_provider": provider,
        "embedding_model": embedding_model,
        "embedding_base_url": base_url if provider == "ollama" else None,
        "query_prefix": getattr(embedder, "query_prefix", ""),
    }
    store.save(metadata, embedded)

    print("\n" + "=" * 60)
    print(f"DONE. {len(embedded)} chunks across {len(by_parent)} parent topics.")
    print(f"Vector store: {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest knowledge/ folder into vector store")
    parser.add_argument("--local", action="store_true",
                        help="Use local SentenceTransformer fallback instead of NVIDIA API")
    parser.add_argument("--provider", default="nvidia",
                        choices=["nvidia", "openai", "ollama", "sentence_transformers"],
                        help="Embedding provider (default: nvidia)")
    parser.add_argument("--model", default=None,
                        help="Embedding model; required for --provider ollama")
    parser.add_argument("--base-url", default="http://127.0.0.1:11434",
                        help="Ollama server URL (default: http://127.0.0.1:11434)")
    parser.add_argument("--query-prefix", default=None,
                        help="Override the model's default query instruction")
    parser.add_argument("--topic", default=None,
                        help="Only ingest one top-level knowledge topic, such as shock_mount")
    parser.add_argument("--output", default=str(STORE_PATH),
                        help="Output JSON vector-store path")
    args = parser.parse_args()
    main(
        use_local=args.local,
        topic=args.topic,
        output_path=Path(args.output),
        provider=args.provider,
        model=args.model,
        base_url=args.base_url,
        query_prefix=args.query_prefix,
    )
