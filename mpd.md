```markdown
# CAD-Aware Engineering Design Assistant (FYP 2024)

An AI-driven Retrieval-Augmented Generation (RAG) system designed to bridge live 3D CAD geometry with Military Standards (MIL-STD) and proprietary engineering calculations. This tool get datas from solidworks api and link back to reference material to choose the right shock mount, generator and equipment rack for first phase for chassis-mounted shelter integration.

## 🏗️ System Architecture (Bridge → Brain → Face) the archetecture serve as example

```text 
┌─────────────────────────────────────────────────────────────┐
│ 1. THE BRIDGE: CAD DATA EXTRACTION (SolidWorks COM API)     │
│  (test_assembly.py / cad_extractor.py)                      │
│  ├─ Mass, Volume, Material Properties                       │
│  ├─ Center of Gravity (X, Y, Z)
│  └─ Bounding Box Dimensions   
└──────────────┬──────────────────────────────────────────────┘
               │ JSON Payload
               ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. THE BRAIN: RAG  ENGINE (LangChain)           │
│  (mil_std_rag.py)                                           │
│  ├─ Vector Store: Ingested MIL-STD-1472H, 810H, 209K PDFs   │
│  ├─ Embedding: NVIDIA/NV-Embed-QA (Chroma/FAISS backend)    │
│  └─ Math Tools: <99000-RandomRMSCalculation> logic          │
└──────────────┬──────────────────────────────────────────────┘
               │ Retrieved Context + CAD Context
               ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. THE FACE: AI DECISION & REPORTING                        │
│  (cad_compliance_checker.py)                                │
│  ├─ LLM: meta/llama-3.1-8b-instruct (via NVIDIA API)        │
│  ├─ Agentic Logic: Cross-references CAD data vs Mil-Specs   │
│  └─ Output: actionable engineering recommendations          │
└─────────────────────────────────────────────────────────────┘

```

## ⚙️ Core Engineering Capabilities

1. **Shock Mount Isolation (MIL-STD-810H):** Extracts assembly mass and cross-references off-road vibration profiles to recommend required Helicoil spring stiffness ($K$) and transmissibility ($T$).
2. **Human Factors & Ergonomics (MIL-STD-1472H):** Extracts the Z-height of CAD bounding boxes (e.g., console tables, heavy drawers)


## 🚀 Setup & Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt

```

*(Ensure you have a valid NVIDIA API Key for embeddings and LLM inference, and that SolidWorks is installed locally for COM API access).*

### 2. Ingest Defense Standards (One-Time Setup)

```bash
python setup_rag.py

```

This script initializes the Vector Database:

* Loads `MIL-STD-1472H.pdf`, `MIL-STD-810H.pdf`, etc.
* Applies `RecursiveCharacterTextSplitter` (1000 chars, 200 overlap to preserve engineering context).
* Generates embeddings and saves the local JSON/Chroma vector store.

## 💻 Usage

### Automated Design Validation

With SolidWorks open and your target assembly (e.g., an equipment rack) active, run:

```bash
python cad_compliance_checker.py

```

This will automatically connect to SolidWorks, extract the metadata, run the semantic search against the MIL-STDs, and output the compliance report.

### Custom Python Integration

```python
from cad_compliance_checker import CADComplianceChecker

checker = CADComplianceChecker(api_key="your-nvidia-api-key")

# The checker automatically pulls active SolidWorks data and appends it to the query
response = checker.check_compliance(
    question="Based on the mass and CG of this cabinet, what capacity Helicoil shock mounts are required for Category 4 vibration?"
)
print(response)

```

## 📊 Example Data Flow

**User Query:** *"Does this console design meet MIL-STD-1472H height requirements?"*

1. **CAD Bridge Extracts:**
* Bounding Box Z-Max: `950mm`
* Assembly Mass: `45kg`


2. **RAG Retrieves:**
* *MIL-STD-1472H, Section 5.9:* "Standard writing console surfaces shall be located at 800mm relative to the seat reference point." (92% match)


3. **LLM Generates Assessment:**
* *"Based on the extracted CAD bounding box (Z-height: 950mm), the current console surface exceeds the MIL-STD-1472H limit of 800mm. ❌ Compliance Failure. Recommendation: Lower the primary shelf surface by 150mm."*



## 🛠️ Future Enhancements (Roadmap)

* **Phase 3 UI:** Migrate CLI output to an interactive **Streamlit Dashboard** for drafters to use seamlessly.
* **Proprietary Excel Integration:** Convert internal ST Engineering math formulas (e.g., `<99000-RandomRMSCalculation.xlsx>`) into Python tool-calling functions for the LangChain agent.
* **Automated Redlining:** Output a visual warning list highlighting out-of-spec dimensions for junior drafters.

```

***

### Why this README update wins:
1. **It drops the academic/tutorial tone:** It uses words like "Chassis-mounted shelter integration", "Payload validation", and "Agentic logic."
2. **It highlights the exact math:** By explicitly mentioning `MIL-STD-810H`, `Transmissibility (T)`, and `Spring Stiffness (K)`, you prove that this is a heavy mechanical engineering project, not just a software script.
3. **It maps to your supervisor's goals:** The "Future Enhancements" section explicitly names his Excel sheet (`<99000-RandomRMSCalculation>`), showing that his specific requirements are actively built into your development roadmap. 

How does this look for your repository's front page?

```