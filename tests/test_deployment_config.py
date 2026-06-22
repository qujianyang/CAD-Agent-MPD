"""Guards the Streamlit Community Cloud (Linux) deployment config.

Catches the exact failure that broke the Cloud build: `pywin32` pinned without a
platform marker (no Linux wheel), an incomplete requirements list, or a Windows-only
import sneaking onto the app's startup path.

Run: .\\mpd\\Scripts\\python.exe -m pytest tests/test_deployment_config.py
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQS = (ROOT / "requirements.txt").read_text(encoding="utf-8")


def _req_lines():
    for raw in REQS.splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            yield line


# Installable specifiers only (comments stripped) — so prose in comments that happens
# to mention an optional package doesn't trip the checks.
REQ_SPECS = "\n".join(_req_lines()).lower()


class TestRequirements:
    def test_pywin32_is_windows_only(self):
        # If pywin32 is present at all, it must carry a Windows platform marker so
        # Linux installs skip it (no Linux wheel exists -> install is unsatisfiable).
        for line in _req_lines():
            if line.lower().startswith("pywin32"):
                assert "platform_system" in line and "Windows" in line, (
                    f"pywin32 must be Windows-only: got {line!r}")

    def test_no_unbuildable_optional_deps(self):
        # These are heavy/optional and NOT imported by the app at runtime; they must
        # not be installed in the Cloud runtime list.
        for pkg in ("pymupdf", "pymupdf4llm", "sentence-transformers"):
            assert pkg not in REQ_SPECS, f"{pkg} should not be a runtime dependency"

    def test_startup_critical_deps_present(self):
        # Imported at app startup -> the app won't boot on Cloud without them.
        for pkg in ("streamlit", "streamlit-float", "pandas", "numpy", "xlrd",
                    "python-dotenv", "langchain-nvidia-ai-endpoints"):
            assert pkg in REQ_SPECS, f"missing startup-critical dependency: {pkg}"


class TestNoWindowsImportsOnStartup:
    # The app shells out to test_assembly.py as a subprocess, so these modules must
    # never import win32com/pythoncom at module level (keeps Linux import safe).
    STARTUP_MODULES = ["app.py", "agent.py", "cad_compliance_checker.py"]
    _WIN_IMPORT = re.compile(r"^\s*(import|from)\s+(win32com|pythoncom)\b", re.MULTILINE)

    def test_no_module_level_win32_imports(self):
        for mod in self.STARTUP_MODULES:
            src = (ROOT / mod).read_text(encoding="utf-8")
            hits = self._WIN_IMPORT.findall(src)
            assert not hits, f"{mod} imports a Windows-only module at top level: {hits}"
