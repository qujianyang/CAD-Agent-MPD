"""
RAG Retriever with Parent Document Retriever Pattern
Integrates with NVIDIA NIM (via OpenAI API standard) for answering questions about NVIDIA courses
"""

from typing import List, Dict, Any
from pathlib import Path
import requests
import time
import sqlite3
import torch
import sys
import os

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

# Fix 1: Use the updated import to avoid deprecation warning
try:
    from langchain_huggingface import HuggingFaceEmbeddings
except ImportError:
    try:
        from langchain_community.embeddings import HuggingFaceEmbeddings
    except ImportError:
        from langchain.embeddings import HuggingFaceEmbeddings

# Add current directory to path for local imports like course_database
sys.path.insert(0, str(Path(__file__).parent))

# Add web_app to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent / 'web_app'))
from config import config

# ============================================================================
# CONFIGURATION - Loaded from environment via config module
# ============================================================================

# API settings
API_BASE_URL = config.OLLAMA_API_URL
MODEL_NAME = config.OLLAMA_MODEL
API_KEY = config.NVIDIA_API_KEY

# Embedding settings (local, no API key needed)
EMBEDDING_MODEL = config.EMBEDDING_MODEL

# Retrieval settings
TOP_K_CHUNKS = config.TOP_K_CHUNKS  # Number of child chunks to retrieve
CHUNK_OVERLAP = config.CHUNK_OVERLAP  # Number of parent docs to return

# LLM generation settings
LLM_TEMPERATURE = config.LLM_TEMPERATURE
LLM_TIMEOUT = config.LLM_TIMEOUT

# ============================================================================

class LLMClient:
    """
    Standardized API Client for LLM interactions.
    Designed to be compatible with OpenAI API format (Ollama, NVIDIA NIM, vLLM).
    """
    def __init__(self, base_url: str, model: str, api_key: str = None, timeout: int = 120):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def chat_completion(self, messages: List[Dict[str, str]], temperature: float = 0.2) -> str:
        """
        Generate a chat completion using the standard /chat/completions endpoint.
        """
        # Handle URL construction carefully
        if self.base_url.endswith('/v1'):
            url = f"{self.base_url}/chat/completions"
        else:
            url = f"{self.base_url}/v1/chat/completions"
        
        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
            "max_tokens": 1024
        }

        print(f"Generating answer with LLM ({self.model})...")
        start = time.time()

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            # Extract content from standard OpenAI response format
            answer = data['choices'][0]['message']['content']

            elapsed = time.time() - start
            print(f"Answer generated in {elapsed:.2f}s")

            return answer.strip()

        except requests.RequestException as e:
            print(f"Error calling LLM API: {e}")
            if hasattr(e, 'response') and e.response:
                 print(f"Response: {e.response.text}")
            return f"Error generating answer: {e}"
        except KeyError as e:
            print(f"Error parsing LLM response: {e}. Data: {data}")
            return "Error parsing model response."


class CourseRAGRetriever:
    """
    RAG system using Parent Document Retriever pattern.

    - Searches child chunks for relevance
    - Returns full parent documents for context
    - Generates answers using LLM Client
    """

    def __init__(self, db_path: str = config.DATABASE_PATH):
        self.db_path = db_path
        
        # Initialize LLM Client (NIM-Ready)
        self.llm_client = LLMClient(
            base_url=API_BASE_URL,
            model=MODEL_NAME,
            api_key=API_KEY,
            timeout=LLM_TIMEOUT
        )
        
        # Fix 2: Don't keep a persistent database connection (threading issue)
        # Create connections as needed instead

        print("Initializing RAG retriever...")
        self.embeddings = self._load_embeddings()
        self.vectorstore, self.parent_map = self._setup_vectorstore()
        print("RAG retriever ready!")

    def _load_embeddings(self):
        """Load local embedding model."""
        print(f"Loading embeddings model: {EMBEDDING_MODEL}")

        # Fix 3: Handle device properly to avoid meta tensor error
        device = 'cuda' if torch.cuda.is_available() else 'cpu'

        # Ensure model loads to the correct device
        model_kwargs = {
            'device': device,
            'trust_remote_code': True  # Allow model to load properly
        }

        # If CPU, ensure no CUDA tensors are created
        if device == 'cpu':
            torch.set_default_tensor_type(torch.FloatTensor)

        return HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs=model_kwargs,
            encode_kwargs={'normalize_embeddings': True, 'device': device}
        )

    def get_course_details(self, course_id: str) -> Dict[str, str]:
        """Get course title and URL by course ID."""
        # Fix 4: Create a new connection for thread safety
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT title, url
            FROM courses
            WHERE id = ?
        """, (course_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {"title": row[0], "url": row[1] or ""}
        return {"title": course_id, "url": ""}

    def _setup_vectorstore(self):
        """Set up vector store with child chunks and parent document mapping."""
        print("Loading parent documents and child chunks from database...")

        # Fix 5: Create a new connection for thread safety
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get all parent documents
        cursor.execute("""
            SELECT id, course_id, content
            FROM parent_documents
            ORDER BY id
        """
        )
        parent_rows = cursor.fetchall()

        # Get all child chunks
        cursor.execute("""
            SELECT id, parent_id, content, chunk_index
            FROM child_chunks
            ORDER BY parent_id, chunk_index
        """
        )
        child_rows = cursor.fetchall()

        # Get all courses for title lookup
        cursor.execute("SELECT id, title FROM courses")
        course_rows = cursor.fetchall()

        conn.close()

        print(f"Loaded {len(parent_rows)} parent docs, {len(child_rows)} child chunks")

        # Create parent document map (parent_id -> parent content)
        # AND course_id -> parent_ids mapping
        parent_map = {}
        self.course_id_to_parent_ids = {}

        for row in parent_rows:
            parent_id = row[0]
            course_id = row[1]
            
            parent_map[parent_id] = {
                'content': row[2],
                'course_id': course_id
            }

            if course_id:
                if course_id not in self.course_id_to_parent_ids:
                    self.course_id_to_parent_ids[course_id] = []
                self.course_id_to_parent_ids[course_id].append(parent_id)

        # Create title -> course_id map for keyword search
        self.courses_map = {}
        for row in course_rows:
            if row[1]: # If title exists
                # Map lowercased title to course ID
                self.courses_map[row[1].lower()] = row[0]

        # Create child documents with parent_id in metadata
        child_docs = []
        for row in child_rows:
            doc = Document(
                page_content=row[2],  # content
                metadata={
                    "parent_id": row[1],  # parent_id
                    "chunk_index": row[3]  # chunk_index
                }
            )
            child_docs.append(doc)

        # Define FAISS index path
        faiss_index_path = Path(__file__).parent / "faiss_index.bin"

        # Create vector store for child chunks
        print("Creating vector store...")
        if faiss_index_path.exists():
            print(f"Loading existing FAISS index from {faiss_index_path}...")
            vectorstore = FAISS.load_local(str(faiss_index_path), self.embeddings, allow_dangerous_deserialization=True)
            print("FAISS index loaded.")
        else:
            print("Creating new FAISS index from documents...")
            vectorstore = FAISS.from_documents(
                documents=child_docs,
                embedding=self.embeddings
            )
            print("FAISS index created. Saving to disk...")
            vectorstore.save_local(str(faiss_index_path))
            print(f"FAISS index saved to {faiss_index_path}.")

        return vectorstore, parent_map

    def query(self, question: str) -> List[Dict[str, Any]]:
        """
        Retrieve relevant parent documents for a question.

        Args:
            question: User's question

        Returns:
            List of parent documents (dicts with content and course_id)
        """
        print(f"\nSearching for: {question}")

        # Search child chunks
        child_docs = self.vectorstore.similarity_search(question, k=TOP_K_CHUNKS)
        print(f"Found {len(child_docs)} matching child chunks")

        # Get unique parent IDs from matching chunks
        parent_ids = set()
        for doc in child_docs:
            parent_id = doc.metadata.get('parent_id')
            if parent_id:
                parent_ids.add(parent_id)

        # --- KEYWORD SEARCH ENHANCEMENT ---
        # Check if the question contains any known course titles
        question_lower = question.lower()
        keyword_matches = []
        
        for title_lower, course_id in self.courses_map.items():
            if title_lower in question_lower:
                print(f"Found title match: '{title_lower}' (ID: {course_id})")
                if course_id in self.course_id_to_parent_ids:
                    # Add all parent docs for this course
                    parent_ids.update(self.course_id_to_parent_ids[course_id])
                    keyword_matches.append(course_id)

        # Retrieve parent documents with course details
        parent_docs = []
        # Convert set to list and ensure we don't exceed a reasonable limit (e.g., CHUNK_OVERLAP + explicit matches)
        # We prioritize keyword matches if we have too many, but generally we just take all unique IDs found
        
        final_parent_ids = list(parent_ids)
        
        # If we have too many, maybe limit? For now, let's just take them all up to a higher limit 
        # or rely on the set to keep it unique. 
        # Let's cap at CHUNK_OVERLAP * 2 to be safe, prioritizing keyword matches?
        # Actually, if a user asks for a specific course, they want THAT course. 
        # So let's just retrieve all found IDs.
        
        for parent_id in final_parent_ids:
            if parent_id in self.parent_map:
                parent_doc = self.parent_map[parent_id].copy()
                # Get course details including URL
                course_id = parent_doc.get('course_id', '')
                if course_id:
                    course_details = self.get_course_details(course_id)
                    parent_doc['course_title'] = course_details['title']
                    parent_doc['course_url'] = course_details['url']
                parent_docs.append(parent_doc)

        print(f"Retrieved {len(parent_docs)} parent documents")
        return parent_docs

    def get_candidate_courses(self, question: str, top_k: int = 10) -> List[str]:
        """
        Performs a semantic search and returns a list of candidate course IDs.
        """
        print(f"\nSearching for candidate courses related to: '{question}'")
        child_docs = self.vectorstore.similarity_search(question, k=top_k)
        
        course_ids = set()
        for doc in child_docs:
            parent_id = doc.metadata.get('parent_id')
            if parent_id and parent_id in self.parent_map:
                course_id = self.parent_map[parent_id].get('course_id')
                if course_id:
                    course_ids.add(course_id)
        
        print(f"Found {len(course_ids)} candidate courses.")
        return list(course_ids)

    def answer_question(self, question: str) -> str:
        """
        Answer a question using RAG, protected by a Regex Guardrail.

        Args:
            question: User's question

        Returns:
            Generated answer from LLM Client or refusal from Guardrail
        """
        # Step 1: Check Guardrails (Regex based)
        competitor_keywords = ["amd", "intel", "radeon", "ryzen"]
        if any(keyword in question.lower() for keyword in competitor_keywords):
            print("Regex Guardrail triggered! Returning refusal.")
            return "As an NVIDIA Learning Assistant, I focus exclusively on NVIDIA technologies like Isaac Sim, Omniverse, and ROS integration. I cannot provide comparisons with other manufacturers."

        # Step 2: Proceed with RAG
        # Retrieve relevant documents
        parent_docs = self.query(question)

        if not parent_docs:
            return "I couldn't find relevant information about that in the NVIDIA course catalog."

        # Build context from parent documents with URLs
        context_parts = []
        course_info_list = []  # Store course info for fallback

        for i, doc in enumerate(parent_docs, 1):
            course_id = doc.get('course_id', 'unknown')
            course_title = doc.get('course_title', course_id)
            course_url = doc.get('course_url', '')
            content = doc.get('content', '')

            # Add course info for context
            context_parts.append(f"[Course {i}: {course_title} ({course_id})]\n{content}\n")

            # Store course info as tuple for fallback mechanism
            if course_url:
                course_info_list.append((course_title, course_url))

        context = "\n---\n".join(context_parts)

        # Build system prompt
        system_message = (
            "You are a Senior NVIDIA AI Learning Advisor. Your goal is to help students choose the right learning path.\n"
            "You will be given a list of courses (Context) and a Student Question.\n\n"
            "### GUIDELINES:\n"
            "1. **Start Strong:** Recommend the best course immediately in the first sentence.\n"
            "2. **Strategic Value:** Explain *why* this fits their specific career goal (e.g., 'For a Robotic Engineer, this is critical because...').\n"
            "3. **Prerequisites (Crucial):** Check if they need to take another course first. If so, warn them clearly.\n"
            "4. **Tone:** Professional, encouraging, and concise.\n\n"
            "### FORMATTING RULES (STRICT):\n"
            "- **Structure:** Use exactly 3 sections: 'Recommendation', 'Why this fits you', and 'Next Steps'.\n"
            "- **Bullet Points:** Use markdown bullet points (-) for lists. Keep them short.\n"
            "- **Spacing:** Do NOT put the list number on its own line. (e.g., Write '1. Step one', NOT '1.\nStep one').\n"
            "- **No Fluff:** Do not repeat the course title multiple times. Be concise.\n\n"
            "### CRITICAL SAFETY RULES:\n"
            "- **STRICT GROUNDING:** Only use info from the Context.\n"
            "- **NO HALLUCINATIONS:** If the context is missing info (like prerequisites), admit it."
        )

        # Build user message with context
        user_message = f"""COURSE INFORMATION:
{context}

USER QUESTION: {question}

ANSWER:"""

        # Generate answer with LLM Client (NIM-Ready)
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]
        
        answer = self.llm_client.chat_completion(messages, temperature=LLM_TEMPERATURE)

        # KISS Fix: Post-process to ensure URLs are included if missing
        # Check if any course URLs are in the response
        has_urls = any(url in answer for _, url in course_info_list)

        # If no URLs found in answer, append them at the end
        if not has_urls and course_info_list:
            answer += "\n\n**Learn more:**\n"
            for title, url in course_info_list:
                answer += f"- {title}: {url}\n"

        return answer

    def close(self):
        """Close database connection."""
        # No persistent connection to close anymore (thread-safe)


def test_retriever():
    """Enhanced test function to verify URL inclusion."""
    retriever = CourseRAGRetriever()

    # Test queries
    test_questions = [
        "What prerequisites do I need for Isaac Sim?",
        "Which courses should I take to learn about robotics?",
        "What are the beginner-friendly NVIDIA courses?"
    ]

    for question in test_questions:
        print("\n" + "="*60)
        print("TEST QUERY")
        print("="*60)
        print(f"Question: {question}")
        
        # Get answer
        answer = retriever.answer_question(question)
        print(f"\nAnswer:\n{answer}")

        # Check if URLs are present in the answer
        if "https://" in answer or "http://" in answer:
            print("\n✓ URLs detected in response")
        else:
            print("\n⚠ No URLs found in response - LLM may need different prompting")

        print("="*60)

    # Test Guardrail for competitor question (now Regex based)
    print("\n" + "="*60)
    print("TEST GUARDRAIL - COMPETITOR QUESTION")
    print("="*60)
    competitor_question = "is amd better than nvidia?"
    guardrailed_answer = retriever.answer_question(competitor_question)
    print(f"\nQuestion: {competitor_question}")
    print(f"Answer:\n{guardrailed_answer}")
    assert "cannot provide comparisons with other manufacturers" in guardrailed_answer, \
           "Guardrail for competitor question failed!"
    print("✓ Guardrail successfully blocked competitor question.")
        
    # Test the new method
    print("\n" + "="*60)
    print("TEST CANDIDATE COURSE RETRIEVAL")
    print("="*60)
    candidate_question = "I want to learn about robotics and Isaac Sim"
    candidate_courses = retriever.get_candidate_courses(candidate_question)
    print(f"Candidate courses for '{candidate_question}': {candidate_courses}")
    assert len(candidate_courses) > 0, "Should find at least one candidate course"

    retriever.close()


if __name__ == "__main__":
    test_retriever()