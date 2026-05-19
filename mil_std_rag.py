"""
RAG query engine combining CAD context with MIL-STD compliance checks.
"""
import requests
from typing import Dict, Any, List
from nvidia_embedder import NVIDIAEmbedder, JSONVectorStore


class MILStandardRAG:
    def __init__(self, api_key: str, vector_store_path: str = "mil_std_embeddings.json"):
        """
        Initialize RAG engine.
        
        Args:
            api_key: NVIDIA API key
            vector_store_path: Path to JSON vector store
        """
        self.api_key = api_key
        self.embedder = NVIDIAEmbedder(api_key)
        self.vector_store = JSONVectorStore(vector_store_path)

    def retrieve_relevant_sections(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieve relevant mil standard sections for a query.
        
        Args:
            query: User query (e.g., "does this design fit weight limits?")
            top_k: Number of relevant sections to retrieve
            
        Returns:
            List of relevant mil standard chunks
        """
        print(f"Retrieving relevant sections for: {query}")
        
        # Generate embedding for query
        query_embedding = self.embedder.embed_text(query)
        
        # Search vector store
        results = self.vector_store.search(query_embedding, top_k=top_k)
        
        return results

    def query_compliance(self, cad_properties: Dict[str, Any], question: str) -> str:
        """
        Query design compliance against mil standards using CAD data.
        
        Args:
            cad_properties: CAD metrics from test_assembly.py (mass, volume, CG, etc.)
            question: Compliance question (e.g., "does this design fit mil standard?")
            
        Returns:
            LLM-generated compliance analysis
        """
        # Retrieve relevant mil standard sections
        relevant_sections = self.retrieve_relevant_sections(question, top_k=5)
        
        # Build context for LLM
        context = self._build_context(cad_properties, relevant_sections)
        
        # Query LLM (via NVIDIA API)
        response = self._query_llm(context, question)
        
        return response

    def _build_context(self, cad_props: Dict[str, Any], mil_sections: List[Dict[str, Any]]) -> str:
        """Build prompt context combining CAD and mil standard data."""
        
        context = f"""
## CAD DESIGN DATA
- Mass: {cad_props.get('mass_kg', 'N/A')} kg
- Volume: {cad_props.get('volume_mm3', 'N/A')} mm³
- Surface Area: {cad_props.get('surface_mm2', 'N/A')} mm²
- Center of Mass: X={cad_props.get('cg_x', 'N/A')}mm, Y={cad_props.get('cg_y', 'N/A')}mm, Z={cad_props.get('cg_z', 'N/A')}mm
- File: {cad_props.get('file_path', 'Unknown')}

## RELEVANT MIL-STD-1472 REQUIREMENTS
"""
        
        for i, section in enumerate(mil_sections, 1):
            context += f"\n### Section {i} (Similarity: {section['similarity']:.2%})\n"
            context += section['content'][:300] + "...\n"
        
        return context

    def _query_llm(self, context: str, question: str) -> str:
        """Query NVIDIA LLM with context and question."""
        
        prompt = f"""{context}

## COMPLIANCE QUESTION
{question}

## ANALYSIS
Based on the CAD design data and MIL-STD-1472 requirements above, provide a compliance assessment.
Include:
1. Whether the design meets the standard
2. Which requirements apply
3. Any risks or concerns
4. Recommendations for improvement
"""
        
        payload = {
            "model": "meta/llama-3.1-8b-instruct",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.2,
            "top_p": 0.7,
            "max_tokens": 1024
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }
        
        url = "https://integrate.api.nvidia.com/v1/chat/completions"
        
        print("Querying LLM for compliance analysis...")
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code != 200:
            return f"Error: {response.status_code} - {response.text}"
        
        data = response.json()
        return data["choices"][0]["message"]["content"]


def extract_cad_properties_from_assembly(assembly_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract relevant properties from test_assembly.py output.
    
    Args:
        assembly_output: Dictionary from test_assembly.py execution
        
    Returns:
        Formatted properties for RAG
    """
    return {
        "mass_kg": assembly_output.get("mass_kg"),
        "volume_mm3": assembly_output.get("volume_mm3"),
        "surface_mm2": assembly_output.get("surface_mm2"),
        "cg_x": assembly_output.get("cg_x"),
        "cg_y": assembly_output.get("cg_y"),
        "cg_z": assembly_output.get("cg_z"),
        "file_path": assembly_output.get("file_path"),
        "doc_type": assembly_output.get("doc_type")
    }
