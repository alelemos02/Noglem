from pydantic import BaseModel
from typing import List, Optional


# Translation Models
class TranslateRequest(BaseModel):
    text: str
    source_lang: str = "auto"
    target_lang: str = "en"
    improve_mode: bool = False


class TranslateResponse(BaseModel):
    original_text: str
    translated_text: str
    improved_text: Optional[str] = None
    detected_language: Optional[str] = None
    source_lang: str
    target_lang: str


# PDF Extraction Models
class TableData(BaseModel):
    page: int
    table_index: int
    headers: List[str]
    rows: List[List[str]]


class ExtractResponse(BaseModel):
    filename: str
    total_pages: int
    tables_found: int
    tables: List[TableData]


class ConvertResponse(BaseModel):
    filename: str
    original_size: int
    converted_size: int
    download_url: str


class FormatResponse(BaseModel):
    filename: str
    original_size: int
    formatted_size: int
    download_url: str


# RAG Models (for future use)
class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    collection_id: Optional[str] = None
    history: Optional[List[ChatMessage]] = None


class ChatResponse(BaseModel):
    response: str
    sources: Optional[List[str]] = None
