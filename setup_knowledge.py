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
  python setup_knowledge.py                # use NVIDIA API embeddings
  python setup_knowledge.py --local        # use local SentenceTransformer fallback
"""
import argparse
import os
import re
import sys
from pathlib import Path
from dotenv import load_dotenv

from nvidia_embedder import NVIDIAEmbedder, JSONVectorStore


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


def collect_chunks(knowledge_dir: Path) -> list[dict]:
    """Walk knowledge/ and build one chunk per .md file."""
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


def main(use_local: bool = False):
    load_dotenv()
    api_key = os.environ.get("NVIDIA_API_KEY", "")
    if not api_key and not use_local:
        print("ERROR: NVIDIA_API_KEY not set. Run with --local or add it to .env.")
        sys.exit(1)

    print("=" * 60)
    print("KNOWLEDGE BASE EMBEDDING PIPELINE")
    print(f"Mode: {'LOCAL EMBEDDINGS' if use_local else 'NVIDIA API'}")
    print(f"Source: {KNOWLEDGE_DIR}")
    print(f"Output: {STORE_PATH}")
    print("=" * 60)

    # 1. Collect chunks from the folder tree
    print("\n[1/3] Walking knowledge/ folder...")
    chunks = collect_chunks(KNOWLEDGE_DIR)
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
    embedder = NVIDIAEmbedder(api_key, use_local=use_local)
    if not use_local:
        if not embedder.test_api_key():
            print("\n  API failed -> falling back to local embeddings.")
            embedder.use_local = True
            use_local = True
    if use_local:
        embedder._init_local_model()

    embedded = embedder.embed_chunks(chunks)

    # 3. Save
    print("\n[3/3] Saving vector store...")
    store = JSONVectorStore(str(STORE_PATH))
    metadata = {
        "source":     "knowledge/",
        "topics":     by_parent,
        "chunk_count": len(embedded),
        "embedding_model": "local" if use_local else "nvidia/llama-nemotron-embed-1b-v2",
    }
    store.save(metadata, embedded)

    print("\n" + "=" * 60)
    print(f"DONE. {len(embedded)} chunks across {len(by_parent)} parent topics.")
    print(f"Vector store: {STORE_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest knowledge/ folder into vector store")
    parser.add_argument("--local", action="store_true",
                        help="Use local SentenceTransformer fallback instead of NVIDIA API")
    args = parser.parse_args()
    main(use_local=args.local)
