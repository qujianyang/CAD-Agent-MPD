# CAD-to-MIL-STD RAG Compliance System

A Retrieval Augmented Generation (RAG) system that combines CAD design properties with MIL-STD-1472 requirements to provide automated compliance analysis.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CAD DESIGN EXTRACTION                     │
│  (test_assembly.py)                                          │
│  ├─ Mass, Volume, Surface Area                              │
│  ├─ Center of Mass (CG)                                     │
│  └─ File Path & Metadata                                    │
└──────────────┬──────────────────────────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────────────────────────┐
│                   DOCUMENT INGESTION                         │
│  (mil_std_chunker.py)                                        │
│  ├─ Extract PDF text via pymupdf4llm                        │
│  ├─ Split into overlapping chunks (500 chars, 100 overlap)  │
│  └─ Generate chunk metadata                                 │
└──────────────┬──────────────────────────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────────────────────────┐
│                NVIDIA EMBEDDINGS API                         │
│  (nvidia_embedder.py)                                        │
│  ├─ Model: nvidia/NV-Embed-QA                              │
│  ├─ Rate-limited API calls                                 │
│  └─ Generate vector embeddings for all chunks              │
└──────────────┬──────────────────────────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────────────────────────┐
│                  JSON VECTOR STORE                           │
│  (mil_std_embeddings.json)                                   │
│  ├─ Store chunks + embeddings                              │
│  ├─ Document metadata                                       │
│  └─ Cosine similarity search                               │
└──────────────┬──────────────────────────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────────────────────────┐
│                  RAG QUERY ENGINE                            │
│  (mil_std_rag.py)                                            │
│  ├─ Embed query                                             │
│  ├─ Retrieve top-5 similar mil standard sections           │
│  ├─ Build context with CAD + MIL-STD data                 │
│  └─ Query NVIDIA LLM (meta/llama-3.1-8b-instruct)         │
└──────────────┬──────────────────────────────────────────────┘
               │
               ↓
┌─────────────────────────────────────────────────────────────┐
│                 COMPLIANCE REPORT                            │
│  (cad_compliance_checker.py)                                 │
│  ├─ Extract CAD properties                                 │
│  ├─ Run RAG query                                          │
│  ├─ Generate compliance assessment                         │
│  └─ Print formatted report                                 │
└─────────────────────────────────────────────────────────────┘
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Ingest MIL-STD PDF (One-time setup)

```bash
python setup_rag.py
```

This will:
- Read `C:\JY Git\MIL-STD-1472H 1.pdf`
- Split into 500-character chunks with 100-char overlap
- Generate embeddings via NVIDIA API
- Save to `mil_std_embeddings.json`

**Time estimate:** 2-5 minutes (depends on PDF size and API rate limits)

## Usage

### Check Design Compliance

```bash
python cad_compliance_checker.py
```

This will:
1. Extract CAD properties from SolidWorks assembly (runs `test_assembly.py`)
2. Query the RAG system for relevant MIL-STD sections
3. Use NVIDIA LLM to generate compliance assessment
4. Print formatted compliance report

### Custom Compliance Questions

```python
from cad_compliance_checker import CADComplianceChecker

checker = CADComplianceChecker(api_key="your-nvidia-api-key")

response = checker.check_compliance(
    question="Does the center of mass fall within acceptable limits?"
)
print(response)
```

## Modules

### `mil_std_chunker.py`
- **`DocumentChunker`**: Ingests PDFs and splits into overlapping chunks
- **Methods**:
  - `ingest_pdf(path)` → Document with chunks
  - `chunk_text(text)` → List of chunks with metadata

### `nvidia_embedder.py`
- **`NVIDIAEmbedder`**: Generates embeddings via NVIDIA API
  - Model: `nvidia/NV-Embed-QA`
  - Includes rate limiting
- **`JSONVectorStore`**: Stores/retrieves embeddings from JSON
  - Supports cosine similarity search
  - Persistent storage

### `mil_std_rag.py`
- **`MILStandardRAG`**: RAG query engine
  - Retrieves relevant mil standard sections
  - Combines CAD context with mil requirements
  - Queries NVIDIA LLM for compliance analysis

### `cad_compliance_checker.py`
- **`CADComplianceChecker`**: Main entry point
  - Runs test_assembly.py to extract CAD data
  - Interfaces with RAG system
  - Generates compliance reports

### `test_assembly.py` (Updated)
- Extracts mass, volume, surface area, and center of mass from SolidWorks assembly
- Handles both `.SLDPRT` (parts) and `.SLDASM` (assemblies)
- Skips part-specific operations on assemblies

## Data Flow Example

```
User asks: "Does this design fit MIL-STD-1472?"
    ↓
CAD Compliance Checker extracts:
  - Mass: 16.5242 kg
  - Volume: 16524182.46 mm³
  - Surface Area: 15915458.77 mm²
  - CG: X=996.73, Y=1361.75, Z=1419.07 mm
    ↓
RAG retrieves relevant sections:
  1. "Weight distribution requirements..." (95% match)
  2. "Center of mass specifications..." (92% match)
  3. "Dimensional limits..." (89% match)
    ↓
LLM generates assessment:
  "Based on CAD data and MIL-STD-1472:
   ✓ Design meets weight requirements
   ✗ Center of mass outside tolerance
   → Recommend repositioning components..."
    ↓
Compliance report printed to console
```

## Configuration

Edit these files to customize:

- **`setup_rag.py`**: PDF path, API key, output store location
- **`cad_compliance_checker.py`**: Custom compliance questions, assembly script path
- **`mil_std_chunker.py`**: Chunk size, overlap, chunking strategy

## Vector Store Format

`mil_std_embeddings.json`:
```json
{
  "metadata": {
    "filename": "MIL-STD-1472H 1.pdf",
    "title": "...",
    "page_count": 250,
    "chunk_count": 1234
  },
  "chunks": [
    {
      "id": 0,
      "content": "Section text...",
      "embedding": [0.123, -0.456, 0.789, ...]
    },
    ...
  ]
}
```

## Error Handling

- **Vector store not found**: Run `setup_rag.py` first
- **NVIDIA API errors**: Check API key, rate limits
- **CAD extraction fails**: Ensure SolidWorks is running and assembly file exists
- **PDF not found**: Update PDF path in `setup_rag.py`

## Performance Notes

- First RAG query: ~30-60 seconds (NVIDIA API calls)
- Subsequent queries: ~5-10 seconds (cached embeddings)
- Chunk embedding: ~1-2 seconds per chunk (with rate limiting)
- JSON vector store: ~50MB for typical MIL-STD document (~200 pages)

## Future Enhancements

- Add caching for repeated queries
- Support multiple mil standards (1472, 1473, etc.)
- Add visualization of compliance violations
- Export reports to PDF
- Real-time design modification suggestions
