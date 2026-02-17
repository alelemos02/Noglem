from langchain_chroma import Chroma
from app.config import settings
from app.services.rag.embedding_service import embedding_service
from typing import List
from langchain_core.documents import Document

class VectorStoreService:
    def __init__(self):
        self.persist_directory = settings.CHROMA_DB_DIR
        self.embedding_function = embedding_service.get_embeddings()
        
        # Initialize Chroma
        self.vector_db = Chroma(
            persist_directory=self.persist_directory,
            embedding_function=self.embedding_function,
            collection_name="pdf_rag_collection"
        )

    def add_documents(self, documents: List[Document]):
        """
        Adds documents to the vector store.
        """
        if not documents:
            return
            
        # Add to Chroma (it automatically persists)
        self.vector_db.add_documents(documents)

    def similarity_search(self, query: str, doc_id: str = None, collection_id: str = None, k: int = 4) -> List[Document]:
        """
        Search for relevant documents. 
        Filter by doc_id OR collection_id.
        """
        filter_dict = None
        if doc_id:
            filter_dict = {"document_id": doc_id}
        elif collection_id:
            filter_dict = {"collection_id": collection_id}

        results = self.vector_db.similarity_search(
            query,
            k=k,
            filter=filter_dict
        )
        return results

    def as_retriever(self, doc_id: str = None, collection_id: str = None, k: int = 20, search_type: str = "mmr"):
        search_kwargs = {
            "k": k,
            "fetch_k": k * 10,
            "lambda_mult": 0.6
        }
        
        # Determine filter
        if doc_id:
            search_kwargs["filter"] = {"document_id": doc_id}
        elif collection_id:
            search_kwargs["filter"] = {"collection_id": collection_id}
            
        return self.vector_db.as_retriever(
            search_type="mmr",
            search_kwargs=search_kwargs
        )

    def delete_documents(self, doc_ids: List[str]):
        """
        Removes documents from the vector store by their IDs (metadata).
        Note: We need to find chunks where metadata['document_id'] is in doc_ids.
        Chroma delete usually works by IDs (chunk IDs), so we might need to query first or delete by where filter if supported.
        Langchain Chroma wrapper supports delete(ids) but not delete(where).
        However, the underlying client supports delete(where).
        """
        if not doc_ids:
            return

        try:
             # Delete usage of where filter on the underlying collection
             # This deletes all chunks associated with this document_id
             for doc_id in doc_ids:
                # Access internal chroma collection
                # Langchain Chroma v0.1+ might expose it differently
                if hasattr(self.vector_db, '_collection'):
                     self.vector_db._collection.delete(where={"document_id": doc_id})
                else: 
                     # Fallback logic if internal structure changes
                     print("Warning: Could not access internal collection for delete(where)")
        except Exception as e:
            print(f"Error deleting from vector store: {e}")

vector_store_service = VectorStoreService()
