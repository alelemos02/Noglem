from langchain_chroma import Chroma
from app.config import settings
from app.services.email.local_embedding_service import get_local_embedding_service
from typing import List
from langchain_core.documents import Document
import logging

logger = logging.getLogger(__name__)


class EmailVectorStoreService:
    def __init__(self):
        self.persist_directory = settings.CHROMA_DB_DIR
        self.embedding_function = get_local_embedding_service().get_embeddings()

        self.vector_db = Chroma(
            persist_directory=self.persist_directory,
            embedding_function=self.embedding_function,
            collection_name=settings.EMAIL_CHROMA_COLLECTION,
        )

    def add_documents(self, documents: List[Document]):
        if not documents:
            return
        self.vector_db.add_documents(documents)

    def similarity_search(
        self, query: str, collection_id: str = None, k: int = 4
    ) -> List[Document]:
        filter_dict = None
        if collection_id:
            filter_dict = {"collection_id": collection_id}

        return self.vector_db.similarity_search(
            query, k=k, filter=filter_dict
        )

    def as_retriever(self, collection_id: str = None, k: int = 20):
        search_kwargs = {
            "k": k,
            "fetch_k": k * 10,
            "lambda_mult": 0.6,
        }

        if collection_id:
            search_kwargs["filter"] = {"collection_id": collection_id}

        return self.vector_db.as_retriever(
            search_type="mmr",
            search_kwargs=search_kwargs,
        )

    def delete_by_collection(self, collection_id: str):
        if not collection_id:
            return
        try:
            if hasattr(self.vector_db, "_collection"):
                self.vector_db._collection.delete(
                    where={"collection_id": collection_id}
                )
        except Exception as e:
            logger.error(f"Erro ao deletar chunks do vector store: {e}")


_email_vector_store_service = None


def get_email_vector_store_service() -> EmailVectorStoreService:
    global _email_vector_store_service
    if _email_vector_store_service is None:
        _email_vector_store_service = EmailVectorStoreService()
    return _email_vector_store_service
