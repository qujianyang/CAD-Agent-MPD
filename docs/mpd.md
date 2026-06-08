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
AD Agent — Next Development Plan
  
     Context

     Current state: working Streamlit app with fixed
     pipeline (CAD extract → physics → catalog → LLM Q&A). 
     Goal: evolve into an agentic tool-use system with a   
     combined CG calculator, better RAG, and
     server-deployable web app.
     Immediate trigger: boss requested combined CG of      
     multi-part assemblies.

     ---
     Build Order (each phase is a usable deliverable)      

     Phase 1 — Combined CG Calculator (boss request, do    
     first)

     New file: cg_calculator.py
     - Component dataclass: name, mass_kg, x_mm, y_mm, z_mm
     - combined_cg(components) -> dict — weighted average  
     formula
     - equipment_db.json — pre-loaded catalog of common    
     items (server racks, UPS, generators, switches) with  
     typical mass + CG offset
     - Streamlit tab in app.py: pick items from DB + set   
     mount position → live CG updates

     Value: engineer builds a rack loadout before
     SolidWorks model exists, sees CG shift in real time.  

     ---
     Phase 2 — Agent Core (tool-use architecture)

     New file: agent.py

     Wrap existing functions as LangChain tools (use @tool 
     decorator, docstring = tool description the LLM       
     reads):

     Tool name: extract_cad_data
     Wraps: cad_compliance_checker.extract_cad_data()      
     Input: file path or "active"
     ────────────────────────────────────────
     Tool name: run_shock_analysis
     Wraps: physics_engine.run_analysis()
     Input: mass_kg, n_bottom, n_wall, env params
     ────────────────────────────────────────
     Tool name: select_isolator
     Wraps: catalog.select_and_analyze()
     Input: mass_kg, mount counts
     ────────────────────────────────────────
     Tool name: calculate_combined_cg
     Wraps: cg_calculator.combined_cg()
     Input: list of components
     ────────────────────────────────────────
     Tool name: lookup_knowledge
     Wraps: mil_std_rag retrieval
     Input: topic string
     ────────────────────────────────────────
     Tool name: list_cad_files
     Wraps: glob scan of a directory
     Input: directory path

     LLM upgrade: change from
     nvidia/llama-3.1-nemotron-nano-8b-v1 to
     meta/llama-3.1-70b-instruct on NVIDIA API — same      
     endpoint, same key, proper tool-calling support.      

     Agent loop: use
     langchain.agents.create_tool_calling_agent +
     AgentExecutor. Replace current rag.query_compliance() 
     call in app.py with agent.invoke({"input": question,  
     "cad_props": props}).

     ---
     Phase 3 — Hierarchical Knowledge Base

     New folder: knowledge/

     knowledge/
       shock_mount/
         summary.md      ← what it is, when to use
         formulas.md     ← V, fn, GT, dD with units        
         selection.md    ← CB1400 table + selection rules  
       generator/
         summary.md
         sizing.md       ← derating, load calcs
       thermal/
         summary.md
         heat_calc.md

     Update nvidia_embedder.py + JSONVectorStore:
     - Add parent_topic field to each chunk at embed time  
     - lookup_knowledge(topic) tool first matches parent   
     folder, then retrieves child chunks
     - Replace setup_rag.py pipeline to walk knowledge/    
     folder instead of one big PDF
     - Each .md file = one chunk (they're intentionally    
     small — no sentence splitting needed)

     Why this beats current approach: no hallucination from
      1000-page PDF context. LLM gets exactly 1-2 pages of 
     authoritative formulas.

     ---
     Phase 4 — Web App Refresh (server-deployable)

     Modify app.py:
     - Remove hard dependency on SolidWorks being running —
      make CAD extraction optional
     - Add 3 tabs:
       - Tab 1: CG Calculator (Phase 1 output) — no        
     SolidWorks needed
       - Tab 2: CAD + Shock Analysis (existing) — needs    
     SolidWorks
       - Tab 3: Agent Chat (Phase 2 output) — ask anything,
      agent picks tools
     - Remove hardcoded API key — .env only, error if      
     missing
     - Add requirements.txt with pinned versions

     Deployment: streamlit run app.py --server.port 8501   
     --server.address 0.0.0.0 — works on any server IT     
     provisions.

     ---
     Files modified / created

     ┌────────────────────┬────────────────────────────────
     ┐
     │        File        │             Action
     │
     ├────────────────────┼────────────────────────────────
     ┤
     │ cg_calculator.py   │ Create
     │
     ├────────────────────┼────────────────────────────────
     ┤
     │ equipment_db.json  │ Create
     │
     ├────────────────────┼────────────────────────────────
     ┤
     │ agent.py           │ Create
     │
     ├────────────────────┼────────────────────────────────
     ┤
     │ knowledge/ folder  │ Create (with .md files per     
     │
     │                    │ topic)
     │
     ├────────────────────┼────────────────────────────────
     ┤
     │                    │ Modify — tabs, agent
     │
     │ app.py             │ integration, remove hardcoded  
     │
     │                    │ key
     │
     ├────────────────────┼────────────────────────────────
     ┤
     │ mil_std_rag.py     │ Modify — lookup_knowledge tool 
     │
     │                    │  wrapper
     │
     ├────────────────────┼────────────────────────────────
     ┤
     │ nvidia_embedder.py │ Modify — add parent_topic      
     │
     │                    │ field
     │
     ├────────────────────┼────────────────────────────────
     ┤
     │ setup_rag.py       │ Modify — walk knowledge/       
     │
     │                    │ folder
     │
     ├────────────────────┼────────────────────────────────
     ┤
     │ requirements.txt   │ Create
     │
     └────────────────────┴────────────────────────────────
     ┘

     ---
     Verification

     - Phase 1: Open app, build a rack with 3 items, verify
      CG shifts correctly when you move one item
     - Phase 2: Ask agent "what isolator for 850kg, 6      
     bottom + 4 wall mounts?" — verify it calls
     run_shock_analysis then select_isolator without being 
     told to
     - Phase 3: Ask about shock mount formulas — verify LLM
      cites knowledge/shock_mount/formulas.md values, not  
     hallucinated numbers
     - Phase 4: Run on port 8501 with --server.address     
     0.0.0.0, connect from another device on same network 