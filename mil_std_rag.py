"""
RAG query engine combining CAD context with MIL-STD compliance checks.
"""
import os
from typing import Dict, Any, List
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.messages import HumanMessage
from nvidia_embedder import NVIDIAEmbedder, JSONVectorStore


class MILStandardRAG:
    def __init__(self, api_key: str, vector_store_path: str = "mil_std_embeddings.json"):
        self.api_key = api_key
        self.embedder = NVIDIAEmbedder(api_key)
        self.vector_store = JSONVectorStore(vector_store_path)
        self.llm = ChatNVIDIA(
            model="nvidia/llama-3.1-nemotron-nano-8b-v1",
            api_key=api_key,
            temperature=0.2,
            top_p=0.7,
            max_tokens=1024,
        )

    def retrieve_relevant_sections(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        print(f"Retrieving relevant sections for: {query}")
        query_embedding = self.embedder.embed_text(query)
        return self.vector_store.search(query_embedding, top_k=top_k)

    def query_compliance(self, cad_properties: Dict[str, Any], question: str) -> str:
        relevant_sections = self.retrieve_relevant_sections(question, top_k=5)
        context = self._build_context(cad_properties, relevant_sections)
        return self._query_llm(context, question)

    def _build_context(self, cad_props: Dict[str, Any], mil_sections: List[Dict[str, Any]]) -> str:
        context = f"""## CAD DESIGN DATA
- Mass: {cad_props.get('mass_kg', 'N/A')} kg
- Volume: {cad_props.get('volume_mm3', 'N/A')} mm³
- Surface Area: {cad_props.get('surface_mm2', 'N/A')} mm²
- Center of Mass: X={cad_props.get('cg_x', 'N/A')}mm, Y={cad_props.get('cg_y', 'N/A')}mm, Z={cad_props.get('cg_z', 'N/A')}mm
- File: {cad_props.get('file_path', 'Unknown')}

## RETRIEVED STANDARD SECTIONS
"""
        for i, section in enumerate(mil_sections, 1):
            context += f"\n### Section {i} (Similarity: {section['similarity']:.2%})\n"
            context += section['content'][:300] + "...\n"
        return context

    def _query_llm(self, context: str, question: str) -> str:
        prompt = f"""{context}

## COMPLIANCE QUESTION
{question}

## ANALYSIS
Based on the CAD design data and retrieved standard sections above, provide a compliance assessment:
1. Whether the design meets the standard
2. Which requirements apply
3. Any risks or concerns
4. Recommendations for improvement
"""
        print("Querying LLM for compliance analysis...")
        response = self.llm.invoke([HumanMessage(content=prompt)])
        return response.content


def extract_cad_properties_from_assembly(assembly_output: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "mass_kg": assembly_output.get("mass_kg"),
        "volume_mm3": assembly_output.get("volume_mm3"),
        "surface_mm2": assembly_output.get("surface_mm2"),
        "cg_x": assembly_output.get("cg_x"),
        "cg_y": assembly_output.get("cg_y"),
        "cg_z": assembly_output.get("cg_z"),
        "file_path": assembly_output.get("file_path"),
        "doc_type": assembly_output.get("doc_type"),
    }


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    API_KEY = os.environ.get("NVIDIA_API_KEY", "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")

    # Sample CAD data to test without SolidWorks
    sample_cad = {
        "mass_kg": 45.0,
        "volume_mm3": 12500000,
        "surface_mm2": 850000,
        "cg_x": 250.0,
        "cg_y": 180.0,
        "cg_z": 420.0,
        "file_path": "test_sample.SLDASM",
    }

    rag = MILStandardRAG(API_KEY)
    response = rag.query_compliance(
        sample_cad,
        question="Based on the mass and CG height, what shock mount stiffness is required for off-road vibration?"
    )
    print("\n" + "=" * 60)
    print(response)
    print("=" * 60)
