import os
import uuid
from typing import Optional, List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct, Record
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from dotenv import load_dotenv

load_dotenv()

COLLECTION_NAME = "research_reports"
EMBEDDING_MODEL = "models/gemini-embedding-001"
VECTOR_SIZE = 3072  # gemini-embedding-001 produces 3072 dimensions
TODO_COLLECTION = "research_todos"
INTERMEDIATE_COLLECTION = "intermediate_reports"

# Adjust distance threshold for what counts as "already processed"
SIMILARITY_THRESHOLD = 0.85

class VectorDBContext:
    def __init__(self):
        url = os.environ.get("QDRANT_URL")
        api_key = os.environ.get("QDRANT_API_KEY")
        
        self.client = QdrantClient(url=url, api_key=api_key) if url else QdrantClient(":memory:")
        self.embeddings = GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL)
        
    def init_db(self):
            collections = [COLLECTION_NAME, TODO_COLLECTION, INTERMEDIATE_COLLECTION]
            for col in collections:
                try:
                    self.client.get_collection(col)
                except Exception:
                    self.client.create_collection(
                        collection_name=col,
                        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
                    )
            
    def _get_embedding(self, text: str) -> list[float]:
        return self.embeddings.embed_query(text)
        
    def search_query(self, query: str) -> Optional[Dict[str, Any]]:
        """Search if a similar query has already been processed.

        Returns a dict with 'report' and optionally 'paper_latex' / 'paper_images'
        keys, or None.
        """
        try:
            vector = self._get_embedding(query)
            results = self.client.query_points(
                collection_name=COLLECTION_NAME,
                query=vector,
                limit=1,
                with_payload=True
            )
            results = results.points
            
            if results and len(results) > 0:
                best_match = results[0]
                if best_match.score >= SIMILARITY_THRESHOLD:
                    hit: Dict[str, Any] = {"report": best_match.payload.get("report", "")}
                    if best_match.payload.get("paper_latex"):
                        hit["paper_latex"] = best_match.payload["paper_latex"]
                    if best_match.payload.get("paper_images"):
                        hit["paper_images"] = best_match.payload["paper_images"]
                    return hit
        except Exception as e:
            print(f"Error searching query: {e}")
            
        return None
        
    def save_report(
        self,
        query: str,
        report: str,
        paper_latex: str | None = None,
        paper_images: list[Dict[str, str]] | None = None,
    ) -> None:
        """Save a new original query, its generated report, and optional LaTeX paper."""
        try:
            vector = self._get_embedding(query)
            point_id = str(uuid.uuid4())
            payload: Dict[str, Any] = {
                "query": query,
                "report": report,
            }
            if paper_latex:
                payload["paper_latex"] = paper_latex
            if paper_images:
                payload["paper_images"] = paper_images
            self.client.upsert(
                collection_name=COLLECTION_NAME,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=payload,
                    )
                ]
            )
        except Exception as e:
            print(f"Error saving report: {e}")

    def get_reports(self) -> List[Dict[str, Any]]:
        """Retrieve all stored queries and reports."""
        try:
            # Scroll through the collection to get items
            results, _ = self.client.scroll(
                collection_name=COLLECTION_NAME,
                limit=100,
                with_payload=True
            )
            reports = []
            for record in results:
                reports.append({
                    "id": record.id,
                    "query": record.payload.get("query"),
                    "report": record.payload.get("report")
                })
            return reports
        except Exception as e:
            print(f"Error getting reports: {e}")
            return []
            
    def save_todos(self, task_id: str, todos: List[str]) -> None:
        """Save task to-dos in Qdrant."""
        try:
            # We just use a dummy vector for pure storage, or embed the task_id
            vector = self._get_embedding(task_id)
            self.client.upsert(
                collection_name=TODO_COLLECTION,
                points=[PointStruct(id=task_id, vector=vector, payload={"todos": todos})]
            )
        except Exception as e:
            print(f"Error saving todos: {e}")

    def update_intermediate_report(self, task_id: str, report_content: str) -> None:
        """Continuously update the intermediate report in Qdrant during research."""
        try:
            vector = self._get_embedding(task_id)
            self.client.upsert(
                collection_name=INTERMEDIATE_COLLECTION,
                points=[PointStruct(id=task_id, vector=vector, payload={"report": report_content})]
            )
        except Exception as e:
            print(f"Error saving intermediate report: {e}")

    def cleanup_task_data(self, task_id: str) -> None:
        """Clean up intermediate and to-do data once research is complete."""
        try:
            self.client.delete(collection_name=TODO_COLLECTION, points_selector=[task_id])
            self.client.delete(collection_name=INTERMEDIATE_COLLECTION, points_selector=[task_id])
            print(f"Cleaned up intermediate data for task: {task_id}")
        except Exception as e:
            print(f"Error cleaning up task data: {e}")
            
    def cleanup(self) -> None:
        """Delete the entire collection to reset the database."""
        try:
            self.client.delete_collection(collection_name=COLLECTION_NAME)
            print(f"Cleaned up collection: {COLLECTION_NAME}")
        except Exception as e:
            print(f"Error cleaning up collection: {e}")
    def cleanup_all(self) -> None:
        """Delete all collections to reset the database."""
        try:
            self.client.delete_collection(collection_name=COLLECTION_NAME)
            self.client.delete_collection(collection_name=TODO_COLLECTION)
            self.client.delete_collection(collection_name=INTERMEDIATE_COLLECTION)
            print("Cleaned up all collections.")
        except Exception as e:
            print(f"Error cleaning up collections: {e}")


