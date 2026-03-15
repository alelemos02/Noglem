import logging
from typing import List, Dict, Generator, Optional
from langchain_openai import ChatOpenAI
from app.config import settings
from app.services.email.email_vector_store import get_email_vector_store_service
from app.services.rag.rerank_service import get_rerank_service

logger = logging.getLogger(__name__)

EMAIL_SYSTEM_PROMPT = (
    "Você é um assistente especializado em buscar e resumir informações de emails corporativos.\n"
    "Sua tarefa é responder perguntas usando APENAS o conteúdo dos emails fornecidos no contexto.\n"
    "\n"
    "DIRETRIZES:\n"
    "1. Responda de forma direta e objetiva.\n"
    "2. Para CADA informação, cite o email fonte no formato: [De: Remetente, DD/MM/YYYY - Assunto: Título]\n"
    "3. Se múltiplos emails tratam do mesmo assunto, sintetize as informações cronologicamente.\n"
    "4. Se não encontrar informação relevante no contexto, diga claramente.\n"
    "5. Preserve dados técnicos (números, datas, nomes) exatamente como aparecem nos emails.\n"
    "6. Ao listar resultados, organize por relevância ou cronologia.\n"
)

EMAIL_SYSTEM_PROMPT_WITH_HISTORY = (
    EMAIL_SYSTEM_PROMPT
    + "\nHISTÓRICO DA CONVERSA:\n"
    "Use o histórico para entender perguntas de acompanhamento.\n\n"
    "Histórico:\n{history}\n"
)


class EmailRAGService:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            openai_api_key=settings.OPENAI_API_KEY,
        )
        self.streaming_llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            openai_api_key=settings.OPENAI_API_KEY,
            streaming=True,
        )

    def _retrieve_and_rerank(
        self,
        question: str,
        collection_id: str,
        k_initial: int = 40,
        k_final: int = 7,
    ) -> List:
        retriever = get_email_vector_store_service().as_retriever(
            collection_id=collection_id,
            k=k_initial,
        )

        initial_docs = retriever.invoke(question)
        logger.info(f"Retrieved {len(initial_docs)} email chunks")

        if not initial_docs:
            return []

        try:
            reranked = get_rerank_service().rerank(question, initial_docs, top_k=k_final)
            if reranked and reranked[0].metadata.get("rerank_score", 0) <= 0.0001:
                reranked = initial_docs[:k_final]
        except Exception as e:
            logger.error(f"Reranking failed: {e}", exc_info=True)
            reranked = initial_docs[:k_final]

        if not reranked and initial_docs:
            reranked = initial_docs[:k_final]

        logger.info(f"Reranked to {len(reranked)} email chunks")
        return reranked

    def _format_history(self, chat_history: List[Dict]) -> str:
        if not chat_history:
            return "Nenhum histórico anterior."
        recent = chat_history[-10:]
        lines = []
        for msg in recent:
            role = "Usuário" if msg.get("role") == "user" else "Assistente"
            content = msg.get("content", "")[:500]
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _build_context(self, docs: List) -> str:
        parts = []
        for doc in docs:
            sender = doc.metadata.get("email_sender", "Desconhecido")
            date = doc.metadata.get("email_date", "")
            subject = doc.metadata.get("email_subject", "Sem assunto")
            content = doc.page_content
            parts.append(
                f"--- Email ---\n"
                f"De: {sender} | Data: {date} | Assunto: {subject}\n"
                f"{content}\n"
            )
        return "\n".join(parts)

    def stream_answer(
        self,
        question: str,
        collection_id: str,
        chat_history: Optional[List[Dict]] = None,
    ) -> Generator[str, None, None]:
        logger.info(f"Email RAG streaming: '{question[:50]}...'")

        docs = self._retrieve_and_rerank(question, collection_id)
        if not docs:
            yield "Não encontrei emails relevantes para responder sua pergunta."
            return

        context = self._build_context(docs)
        has_history = bool(chat_history and len(chat_history) > 0)

        if has_history:
            system = EMAIL_SYSTEM_PROMPT_WITH_HISTORY.replace(
                "{history}", self._format_history(chat_history)
            )
        else:
            system = EMAIL_SYSTEM_PROMPT

        system += f"\n\nContexto dos Emails:\n{context}"

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ]

        try:
            for chunk in self.streaming_llm.stream(messages):
                if chunk.content:
                    yield chunk.content
        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            yield f"\n\n[Erro ao gerar resposta: {str(e)}]"

        logger.info("Email RAG streaming completed")

    def get_answer(
        self,
        question: str,
        collection_id: str,
        chat_history: Optional[List[Dict]] = None,
    ) -> str:
        logger.info(f"Email RAG answer: '{question[:50]}...'")

        docs = self._retrieve_and_rerank(question, collection_id)
        if not docs:
            return "Não encontrei emails relevantes para responder sua pergunta."

        context = self._build_context(docs)
        has_history = bool(chat_history and len(chat_history) > 0)

        if has_history:
            system = EMAIL_SYSTEM_PROMPT_WITH_HISTORY.replace(
                "{history}", self._format_history(chat_history)
            )
        else:
            system = EMAIL_SYSTEM_PROMPT

        system += f"\n\nContexto dos Emails:\n{context}"

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ]

        response = self.llm.invoke(messages)
        return response.content


_email_rag_service = None


def get_email_rag_service() -> EmailRAGService:
    global _email_rag_service
    if _email_rag_service is None:
        _email_rag_service = EmailRAGService()
    return _email_rag_service
