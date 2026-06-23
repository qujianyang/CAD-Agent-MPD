"""
CAD-to-RAG Compliance Query Interface.
1. Extracts live CAD data from SolidWorks via test_assembly.py
2. Shows extracted properties to the user
3. Prompts user for an engineering question
4. Returns RAG + LLM response
"""
import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv
# NOTE: `from mil_std_rag import MILStandardRAG` is intentionally NOT imported here.
# It pulls in torch + transformers, and the only code that needs it is the CLI demo
# in the __main__ block below. Importing it at module top would load the whole ML
# stack on every Streamlit startup (app.py imports _parse_cad_output from here), even
# though the app never uses MILStandardRAG. It is imported lazily where it's used.


def extract_cad_data(
    assembly_script: str = "test_assembly.py",
    file_path: str | None = None,
) -> dict:
    """
    Run test_assembly.py in a subprocess and parse CAD properties from its stdout.

    Args:
        assembly_script: The SolidWorks COM driver script. Don't change unless
                         you've copied it somewhere else.
        file_path: Optional absolute path to a .SLDASM or .SLDPRT file to open.
                   If None, test_assembly.py will use the currently active
                   SolidWorks document.
    """
    print("[1/3] Connecting to SolidWorks and extracting CAD data...")
    cmd = [sys.executable, assembly_script]
    if file_path:
        cmd += ["--file", file_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
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
    components = []
    in_bom = False

    for line in output.split("\n"):
        line_stripped = line.strip()
        try:
            # Mass properties
            if "-> Mass:" in line_stripped:
                props["mass_kg"] = float(line_stripped.split()[2])
            elif "-> Volume:" in line_stripped:
                props["volume_mm3"] = float(line_stripped.split()[2])
            elif "-> Surface Area:" in line_stripped:
                props["surface_mm2"] = float(line_stripped.split()[3])

            # CG from base (preferred — this is what physics_engine consumes).
            # Must be checked BEFORE "Center of Mass (CG, raw)" because the
            # phrase "Center of Mass" doesn't appear in this line.
            elif "CG from Base:" in line_stripped:
                props["cg_x_base"] = float(line_stripped.split("X=")[1].split("mm")[0])
                props["cg_y_base"] = float(line_stripped.split("Y=")[1].split("mm")[0])
                props["cg_z_base"] = float(line_stripped.split("Z=")[1].split("mm")[0])

            # Raw CG (default origin frame — kept for reference/debugging).
            elif "Center of Mass (CG" in line_stripped:
                props["cg_x"] = float(line_stripped.split("X=")[1].split("mm")[0])
                props["cg_y"] = float(line_stripped.split("Y=")[1].split("mm")[0])
                props["cg_z"] = float(line_stripped.split("Z=")[1].split("mm")[0])

            # Which coordinate system the raw CG is reported in.
            elif "-> Coord System:" in line_stripped:
                props["coord_sys_used"] = line_stripped.split("Coord System:")[1].strip()

            # Bounding envelope: OK (W:560.0mm x D:2000.0mm x H:1000.0mm)
            elif "W:" in line_stripped and "D:" in line_stripped and "H:" in line_stripped:
                props["width_mm"]  = float(line_stripped.split("W:")[1].split("mm")[0])
                props["depth_mm"]  = float(line_stripped.split("D:")[1].split("mm")[0])
                props["height_mm"] = float(line_stripped.split("H:")[1].split("mm")[0])

            # Bounding box min/max corners
            elif "-> BBox Min:" in line_stripped:
                props["bbox_x_min"] = float(line_stripped.split("X=")[1].split("mm")[0])
                props["bbox_y_min"] = float(line_stripped.split("Y=")[1].split("mm")[0])
                props["bbox_z_min"] = float(line_stripped.split("Z=")[1].split("mm")[0])
            elif "-> BBox Max:" in line_stripped:
                props["bbox_x_max"] = float(line_stripped.split("X=")[1].split("mm")[0])
                props["bbox_y_max"] = float(line_stripped.split("Y=")[1].split("mm")[0])
                props["bbox_z_max"] = float(line_stripped.split("Z=")[1].split("mm")[0])

            # File path
            elif "Path:" in line_stripped and "Saved:" in line_stripped:
                props["file_path"] = line_stripped.split("Path: ")[1].split(",")[0].strip()

            # BOM section marker
            elif "Iterating Assembly Components" in line_stripped:
                in_bom = True

            # Component entries: "  -> Name" (no colon after name)
            elif in_bom and line_stripped.startswith("->") and ":" not in line_stripped:
                name = line_stripped.lstrip("-> ").strip()
                if name and "..." not in name:
                    components.append(name)

            # Stop BOM collection when next DEBUG section starts
            elif in_bom and "[DEBUG]" in line_stripped and "Iterating" not in line_stripped:
                in_bom = False

        except (IndexError, ValueError):
            pass

    if components:
        props["components"] = components
        props["component_count"] = len(components)

    return props


def print_cad_summary(props: dict):
    """Print extracted CAD properties in a readable format."""
    print("\n  Extracted CAD Properties:")
    print(f"    Mass:          {props.get('mass_kg', 'N/A')} kg")
    print(f"    Volume:        {props.get('volume_mm3', 'N/A')} mm³")
    print(f"    Surface Area:  {props.get('surface_mm2', 'N/A')} mm²")
    print(f"    Envelope:      W={props.get('width_mm','N/A')}mm  D={props.get('depth_mm','N/A')}mm  H={props.get('height_mm','N/A')}mm")
    print(f"    CG:            X={props.get('cg_x','N/A')}mm  Y={props.get('cg_y','N/A')}mm  Z={props.get('cg_z','N/A')}mm")
    if props.get("components"):
        print(f"    Components ({props['component_count']}): {', '.join(props['components'])}")
    print(f"    File:          {props.get('file_path', 'Unknown')}")


if __name__ == "__main__":
    load_dotenv()
    API_KEY = os.environ.get("NVIDIA_API_KEY", "").strip()
    if not API_KEY:
        print("ERROR: NVIDIA_API_KEY not set. Add it to your .env file.")
        raise SystemExit(1)

    if not Path("artifacts/mil_std_embeddings.json").exists():
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

    # Step 3: RAG query  (heavy import deferred to here — see note at top of file)
    print("\n[3/3] Querying RAG engine...")
    from mil_std_rag import MILStandardRAG
    rag = MILStandardRAG(API_KEY)
    response = rag.query_compliance(cad_props, question)

    print("\n" + "=" * 60)
    print(response)
    print("=" * 60)
