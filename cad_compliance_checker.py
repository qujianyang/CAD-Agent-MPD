"""
CAD-to-MIL-STD Compliance Query Interface.
Combines CAD properties with RAG to check design compliance.
"""
import subprocess
import json
from pathlib import Path
from mil_std_rag import MILStandardRAG, extract_cad_properties_from_assembly


class CADComplianceChecker:
    def __init__(self, api_key: str, assembly_script: str = "test_assembly.py"):
        """
        Initialize compliance checker.
        
        Args:
            api_key: NVIDIA API key
            assembly_script: Path to test_assembly.py
        """
        self.api_key = api_key
        self.assembly_script = assembly_script
        self.rag = MILStandardRAG(api_key)

    def extract_cad_data(self) -> dict:
        """
        Run test_assembly.py and extract properties from output.
        
        Returns:
            CAD properties dict
        """
        print("Extracting CAD data from assembly...")
        
        try:
            result = subprocess.run(
                ["python", self.assembly_script],
                capture_output=True,
                text=True,
                cwd=Path(self.assembly_script).parent
            )
            
            output = result.stdout
            print("CAD extraction output:")
            print(output[:500] + "..." if len(output) > 500 else output)
            
            # Parse the raw array data from output
            cad_props = self._parse_cad_output(output)
            return cad_props
            
        except Exception as e:
            print(f"Error running assembly script: {e}")
            return {}

    def _parse_cad_output(self, output: str) -> dict:
        """Extract CAD properties from test_assembly.py output."""
        props = {}
        
        # Extract mass
        if "Mass:" in output:
            for line in output.split("\n"):
                if "Mass:" in line:
                    parts = line.split()
                    if len(parts) > 1:
                        props["mass_kg"] = float(parts[2])
                elif "Volume:" in line:
                    parts = line.split()
                    if len(parts) > 1:
                        props["volume_mm3"] = float(parts[2])
                elif "Surface Area:" in line:
                    parts = line.split()
                    if len(parts) > 1:
                        props["surface_mm2"] = float(parts[3])
                elif "Center of Mass" in line:
                    # Parse CG values
                    if "X=" in line:
                        try:
                            x_str = line.split("X=")[1].split("mm")[0]
                            y_str = line.split("Y=")[1].split("mm")[0]
                            z_str = line.split("Z=")[1].split("mm")[0]
                            props["cg_x"] = float(x_str)
                            props["cg_y"] = float(y_str)
                            props["cg_z"] = float(z_str)
                        except:
                            pass
        
        # Extract file path
        if "Path:" in output:
            for line in output.split("\n"):
                if "Path:" in line:
                    parts = line.split("Path: ")
                    if len(parts) > 1:
                        props["file_path"] = parts[1].split(",")[0]
        
        return props

    def check_compliance(self, question: str = "Does this design fit MIL-STD-1472?") -> str:
        """
        Check CAD design compliance against MIL-STD.
        
        Args:
            question: Specific compliance question
            
        Returns:
            LLM-generated compliance analysis
        """
        # Get CAD data
        cad_props = self.extract_cad_data()
        
        if not cad_props:
            return "ERROR: Could not extract CAD properties"
        
        print(f"\nCAD Properties extracted:")
        for key, value in cad_props.items():
            print(f"  {key}: {value}")
        
        # Query RAG with CAD context
        print(f"\nQuerying compliance: {question}")
        response = self.rag.query_compliance(cad_props, question)
        
        return response


def format_compliance_report(response: str) -> str:
    """Format LLM response as a compliance report."""
    return f"""
{'=' * 70}
MIL-STD-1472 COMPLIANCE ANALYSIS
{'=' * 70}
{response}
{'=' * 70}
"""


if __name__ == "__main__":
    import sys
    
    # Configuration
    API_KEY = "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"
    
    # Check that vector store exists
    if not Path("mil_std_embeddings.json").exists():
        print("ERROR: Vector store not found!")
        print("Run: python setup_rag.py")
        sys.exit(1)
    
    # Initialize checker
    checker = CADComplianceChecker(API_KEY)
    
    # Run compliance check
    response = checker.check_compliance(
        question="Does this design fit MIL-STD-1472 requirements for weight, center of mass, and dimensions?"
    )
    
    # Print formatted report
    print(format_compliance_report(response))
