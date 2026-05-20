"""
CAD-to-RAG Compliance Query Interface.
1. Extracts live CAD data from SolidWorks via test_assembly.py
2. Shows extracted properties to the user
3. Prompts user for an engineering question
4. Returns RAG + LLM response
"""
import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from mil_std_rag import MILStandardRAG


def extract_cad_data(assembly_script: str = "test_assembly.py") -> dict:
    """Run test_assembly.py and parse CAD properties from its stdout."""
    print("[1/3] Connecting to SolidWorks and extracting CAD data...")
    try:
        result = subprocess.run(
            ["python", assembly_script],
            capture_output=True,
            text=True,
        )
        output = result.stdout
        if result.returncode != 0:
            print(f"  Warning: script exited with code {result.returncode}")
            if result.stderr:
                print(f"  Stderr: {result.stderr[:200]}")
        return _parse_cad_output(output)
    except Exception as e:
        print(f"  ERROR running {assembly_script}: {e}")
        return {}


def _parse_cad_output(output: str) -> dict:
    """Parse the printed output of test_assembly.py into a dict."""
    props = {}
    for line in output.split("\n"):
        line = line.strip()
        try:
            if "-> Mass:" in line:
                props["mass_kg"] = float(line.split()[2])
            elif "-> Volume:" in line:
                props["volume_mm3"] = float(line.split()[2])
            elif "-> Surface Area:" in line:
                props["surface_mm2"] = float(line.split()[3])
            elif "Center of Mass (CG):" in line:
                props["cg_x"] = float(line.split("X=")[1].split("mm")[0])
                props["cg_y"] = float(line.split("Y=")[1].split("mm")[0])
                props["cg_z"] = float(line.split("Z=")[1].split("mm")[0])
            elif "Path:" in line and "Saved:" in line:
                props["file_path"] = line.split("Path: ")[1].split(",")[0].strip()
        except (IndexError, ValueError):
            pass
    return props


def print_cad_summary(props: dict):
    """Print extracted CAD properties in a readable format."""
    print("\n  Extracted CAD Properties:")
    print(f"    Mass:          {props.get('mass_kg', 'N/A')} kg")
    print(f"    Volume:        {props.get('volume_mm3', 'N/A')} mm³")
    print(f"    Surface Area:  {props.get('surface_mm2', 'N/A')} mm²")
    print(f"    CG:            X={props.get('cg_x','N/A')}mm  Y={props.get('cg_y','N/A')}mm  Z={props.get('cg_z','N/A')}mm")
    print(f"    File:          {props.get('file_path', 'Unknown')}")


if __name__ == "__main__":
    load_dotenv()
    API_KEY = os.environ.get(
        "NVIDIA_API_KEY",
        "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"
    )

    if not Path("mil_std_embeddings.json").exists():
        print("ERROR: Vector store not found. Run: python setup_rag.py")
        raise SystemExit(1)

    # Step 1: Get CAD data
    cad_props = extract_cad_data()
    if not cad_props:
        print("ERROR: Could not extract CAD properties. Is SolidWorks open with a model loaded?")
        raise SystemExit(1)

    print_cad_summary(cad_props)

    # Step 2: Ask user for question
    print("\n[2/3] Enter your engineering question (or press Enter for default):")
    question = input("  > ").strip()
    if not question:
        question = (
            "Based on the mass and CG height, what shock mount or isolator is recommended "
            "for off-road vehicular vibration?"
        )
        print(f"  Using default: {question}")

    # Step 3: RAG query
    print("\n[3/3] Querying RAG engine...")
    rag = MILStandardRAG(API_KEY)
    response = rag.query_compliance(cad_props, question)

    print("\n" + "=" * 60)
    print(response)
    print("=" * 60)
