# Local LLM Evaluation Environment

Status: Verified baseline  
Recorded: 2026-07-12  
Timezone: Asia/Singapore

## Hardware

| Component | Verified value | Verification |
|---|---|---|
| CPU | Intel Core Ultra 9 275HX | Windows processor registry |
| System RAM | 31.4 GiB usable | .NET `ComputerInfo` |
| GPU | NVIDIA GeForce RTX 5080 Laptop GPU | `nvidia-smi` |
| GPU VRAM | 16,303 MiB | `nvidia-smi` |
| NVIDIA driver | 591.91 | `nvidia-smi` |
| CUDA compatibility reported by driver | 13.1 | `nvidia-smi` |

## Operating system

- Windows NT version: `10.0.26200.0`
- Display version: `25H2`
- Build: `26200.8655`
- Architecture/runtime family: Win32NT
- The Windows registry product-name label reports `Windows 10 Home China`, while
  the build and project inventory identify the Windows 11 generation. The exact
  edition label should be confirmed from Windows Settings before the report is
  finalized; the build number above is the reproducible environment identifier.

## Local serving

| Item | Value |
|---|---|
| Serving backend | Ollama, Windows native |
| Ollama version | 0.31.2 |
| Local API | `http://localhost:11434/v1` |
| API compatibility path | OpenAI-compatible chat completions via `ChatOpenAI` |
| Current application provider | `ollama` |
| Current application model | `gemma4:12b` |

Ollama is the practical backend currently used by the application and the three
candidate models are installed. The same backend version must be used for all
formal screening runs. Moving to vLLM later would be a separate backend study or
would require rerunning every candidate.

## Installed candidate models

| Ollama tag | Family | Parameters | Quantization | Stored size | Digest |
|---|---|---:|---|---:|---|
| `qwen3:14b` | qwen3 | 14.8B | Q4_K_M GGUF | 9.28 GB | `bdbd181c33f2ed1b31c972991882db3cf4d192569092138a7d29e973cd9debe8` |
| `qwen3.5:9b` | qwen35 | 9.7B | Q4_K_M GGUF | 6.59 GB | `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7` |
| `gemma4:12b` | gemma4 | 11.9B | Q4_K_M GGUF | 7.56 GB | `4eb23ef187e2c5462566d6a1d3bbbc2f1346d0b4327cbb66d58fffbcc9b2b05c` |

Stored size is the Ollama artifact size, not peak inference VRAM. Peak VRAM will
be measured during screening and final runs.

## Application integration

- `llm_config.py` supports `LLM_PROVIDER=ollama`, an Ollama model tag, and the
  local OpenAI-compatible base URL.
- `agent.py` builds Ollama through `ChatOpenAI` and currently hard-codes
  `temperature=0.1` and `max_tokens=2048`.
- The application does not currently pass an explicit context length, seed,
  thinking-mode control, or single/parallel-tool-call setting to Ollama.
- These gaps must be resolved and verified before the screening configuration
  can be marked frozen.

## Python environment

The repository-local virtual environment declares:

- intended Python version: 3.10.8;
- base interpreter path: `C:\Users\qujia\AppData\Local\Programs\Python\Python310`;
- virtual environment: `mpd\`.

Current verification result:

- the base interpreter file exists at the recorded path;
- activating `mpd\Scripts\Activate.ps1` succeeds in the user's PowerShell;
- the user's `python where(...)` command launched Python successfully, after
  which Python correctly reported that `where` was not a script file;
- the Windows `py` launcher does not list the installation, but launcher
  registration is not required when the repository venv works; and
- the Codex command sandbox cannot execute or enumerate this AppData Python
  directory because access is denied, so it cannot independently run the venv.

The earlier sandbox result must not be interpreted as a missing Python
installation. The activated user terminal was verified with:

```powershell
python --version
python -c "import sys; print(sys.executable)"
python -m pip --version
```

These checks report Python 3.10.8, the `mpd` interpreter, and a working venv pip.

Verified output on 2026-07-12:

- Python: `3.10.8`
- Executable: `C:\Users\qujia\Documents\GitHub\CAD-Agent-MPD\mpd\Scripts\python.exe`
- pip: `26.1.2` from the repository-local `mpd` environment

## Security and reproducibility

- API keys remain in `.env` and must never be copied into evaluation records.
- Raw run records must contain provider/model identifiers, but no credentials.
- `requirements.txt`, relevant source hashes, Ollama version, model digests, and
  environment settings will be captured at final freeze.
- Test dependencies are pinned separately in `requirements-dev.txt`.
