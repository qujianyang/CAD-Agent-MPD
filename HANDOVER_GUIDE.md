# Project Handover Guide

## 1. Project purpose

This project is a Streamlit engineering assistant that makes repetitive
mechanical-engineering checks faster, more consistent, and easier to review.

Its main application is shock-isolator selection for vehicle-mounted equipment
and server racks. The user enters the equipment mass, rack mass, mount
configuration, shock environment, clearance, and design limits. The application
then:

1. Runs deterministic Python calculations for four shock load cases.
2. Checks transmitted acceleration, isolator movement, static capacity, and
   installation clearance.
3. Selects or verifies a suitable wire-rope isolator from the available
   catalogue data.
4. Reports the governing load case, PASS/FAIL result, assumptions, and warnings.
5. Generates supporting outputs such as a supplier enquiry pack and explanatory
   visual.

The application also contains tie-down and vehicle-mobility analysis tabs.
SolidWorks can optionally supply mass, centre of gravity, and bounding-box
information on a Windows computer.

## 2. Role of the AI assistant

The AI assistant does not replace the engineering calculations. It interprets
the user's question, chooses the appropriate Python tool, explains the
calculated result, and retrieves supporting information from the local
engineering knowledge base.

The main design principle is:

```text
LLM decides how to respond
        |
        v
Python tools perform engineering calculations
        |
        v
RAG provides standards, catalogue, workflow, and limitation references
```

The deterministic Python result remains authoritative for numerical values and
PASS/FAIL decisions. Supplier confirmation and physical qualification are still
required before an isolator is approved for a real installation.

In the Shock Selector tab, the assistant can operate in two modes:

- **Linked mode:** receives the current selector result and explains it.
- **General mode:** does not receive the selected isolator and can answer a
  separate general question.

Use the **Use current selector result** switch to change between these modes.

## 3. Important repository locations

| Location | Purpose |
|---|---|
| `app.py` | Main Streamlit application |
| `agent.py` | AI agents, engineering tools, and RAG tool |
| `physics_engine.py` | Shock-isolation calculations |
| `catalog.py` | Isolator catalogue selection and verification |
| `knowledge/shock_mount/` | Shock-mount RAG source documents |
| `artifacts/knowledge_embeddings_openai.json` | OpenAI production vector store |
| `requirements.txt` | Runtime Python dependencies |
| `requirements-dev.txt` | Runtime dependencies plus test tools |
| `tests/` | Automated test suite |
| `docs/STREAMLIT_CLOUD_DEPLOYMENT.md` | Streamlit Cloud deployment notes |

## 4. New-computer setup

### 4.1 Prerequisites

Install:

- Git
- Python 3.10, 64-bit
- Visual Studio Code or another editor
- SolidWorks only if live CAD extraction is required

Python 3.10.8 is the verified project version. During Python installation,
enable **Add python.exe to PATH**.

The GitHub repository is private. The new user must have permission to access:

```text
https://github.com/qujianyang/CAD-Agent-MPD
```

### 4.2 Clone the project

Open PowerShell:

```powershell
git clone --branch PDF-Ingestion https://github.com/qujianyang/CAD-Agent-MPD.git
cd CAD-Agent-MPD
```

### 4.3 Create the virtual environment

Confirm that Python 3.10 is available:

```powershell
py -3.10 --version
```

Create the repository-local environment:

```powershell
py -3.10 -m venv mpd
```

Install the dependencies:

```powershell
.\mpd\Scripts\python.exe -m pip install --upgrade pip
.\mpd\Scripts\python.exe -m pip install -r requirements.txt
```

Always use `.\mpd\Scripts\python.exe` for this project. This avoids accidentally
running scripts with a different system Python installation.

### 4.4 Configure the AI services

Create a file named `.env` in the repository root:

```dotenv
LLM_PROVIDER=openai
OPENAI_API_KEY=replace-with-the-approved-project-key
OPENAI_MODEL=gpt-5.4-mini

EMBEDDING_PROVIDER=openai
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
KNOWLEDGE_STORE_PATH=artifacts/knowledge_embeddings_openai.json

OPENAI_IMAGE_MODEL=gpt-image-2
```

Use only the approved project API key. Never commit `.env`, paste the key into
source code, or include it in screenshots.

The calculators and deterministic report generators can run without an API key,
but the AI assistant, OpenAI retrieval queries, and image generation require it.

## 5. Start the application

From the repository root, run:

```powershell
.\mpd\Scripts\python.exe -m streamlit run app.py
```

The browser should open automatically. Otherwise, open:

```text
http://localhost:8501
```

Stop the application with `Ctrl+C` in PowerShell.

## 6. Basic smoke test

After starting the application:

1. Open **Shock selector**.
2. Use the default 850 kg total mass and 6-bottom plus 4-wall mount case.
3. Select the best isolator.
4. Confirm that a part, four load cases, governing constraint, and PASS/FAIL
   result are displayed.
5. Leave **Use current selector result** enabled and ask the assistant to explain
   the result.
6. Disable the switch and ask a general question such as:
   `Why does natural frequency affect shock isolation?`
7. Generate a supplier enquiry pack and confirm that the Word file downloads.

Image generation is optional and uses the paid OpenAI Image API.

## 7. Run the automated tests

Install the development dependencies:

```powershell
.\mpd\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Run all tests:

```powershell
.\mpd\Scripts\python.exe -m pytest -q
```

The last verified result before this handover was:

```text
477 passed, 9 skipped
```

## 8. Deployment notes

The application is deployed on Streamlit Community Cloud from:

```text
Repository: qujianyang/CAD-Agent-MPD
Branch: PDF-Ingestion
Entry point: app.py
Python: 3.10
```

Pushing a new commit to `PDF-Ingestion` triggers a Streamlit Cloud redeployment.
Cloud secrets are configured in the Streamlit application settings and must not
be committed to Git.

The cloud server runs Linux, so live SolidWorks COM extraction is unavailable
there. The Shock Selector, engineering tools, RAG assistant, reports, and
explanatory-image features remain available.

## 9. Engineering and security boundaries

- Treat the application as engineering decision support, not final approval.
- Numerical answers must come from the deterministic Python tools.
- Vendor simulation is not the same as physical qualification.
- A shock PASS does not prove random-vibration compliance.
- Supplier confirmation and installation testing remain required.
- Keep the repository and deployed application private unless release is
  explicitly approved.
- OpenAI receives approved user prompts, tool outputs, retrieved excerpts, and
  optional image prompts while those cloud features are used.

