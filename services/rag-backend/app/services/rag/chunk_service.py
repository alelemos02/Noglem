from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from typing import List, Dict

class ChunkService:
    def __init__(self, chunk_size=4000, chunk_overlap=500):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", " ", ""]
        )

    def create_chunks(self, extracted_data: List[Dict], doc_id: str) -> List[Document]:
        """
        Splits extracted text into chunks with metadata.
        """
        documents = []
        for item in extracted_data:
            text = item["text"]
            page_number = item["page_number"]
            
            # Create LangChain Documents for this page
            page_docs = self.text_splitter.create_documents(
                texts=[text],
                metadatas=[{
                    "document_id": doc_id,
                    "page_number": page_number
                }]
            )
            documents.extend(page_docs)
            
        return documents

chunk_service = ChunkService()
