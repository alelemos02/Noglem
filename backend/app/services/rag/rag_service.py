"""
RAG Service with streaming support, conversation memory, and structured logging.
"""
import logging
from typing import List, Dict, Generator, Optional
from langchain_openai import ChatOpenAI
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage
from app.config import settings
from app.services.rag.vector_store import vector_store_service
from app.services.rag.rerank_service import rerank_service

logger = logging.getLogger(__name__)

class RAGService:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            openai_api_key=settings.OPENAI_API_KEY
        )
        self.streaming_llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0,
            openai_api_key=settings.OPENAI_API_KEY,
            streaming=True
        )

    def _get_system_prompt(self, with_history: bool = False) -> str:
        """Generate system prompt with optional conversation history context."""
        base_prompt = (
            "Você é um analista de IA sênior e engenheiro de sistemas (Persona: NotebookLM/Deep Researcher).\n"
            "Sua tarefa é sintetizar documentos técnicos em narrativas ricas, estruturadas e densas.\n"
            "\n"
            "ESTRUTURA DE RESPOSTA (Estilo Deep Dive):\n"
            "- Se o usuário pedir um RESUMO ou PRINCIPAIS PONTOS, use uma estrutura numerada (1, 2, 3...) com títulos em negrito.\n"
            "- Para cada ponto, escreva um parágrafo denso explicando o 'Porquê', o 'Como' e as 'Consequências'. Não seja superficial.\n"
            "- Conecte os pontos: Mostre como o ponto 1 afeta o ponto 3.\n"
            "- **INTRODUÇÃO**: Comece com um parágrafo de introdução contextualizando o tema.\n"
            "- **CONCLUSÃO**: Termine com um parágrafo de síntese ou reflexão final.\n"
            "\n"
            "DIRETRIZES DE QUALIDADE:\n"
            "1. **Visão Holística**: Identifique os 'Grandes Temas' (ex: Geopolítica, Riscos, Economia) mesmo que estejam espalhados.\n"
            "2. **Analogias**: Se útil, use analogias (ex: 'Imagine uma corrida de cavalos...') para fixar o conceito.\n"
            "3. **Citações (OBRIGATÓRIO)**: Para CADA afirmação técnica ou fática, você DEVE incluir a citação imediatamente após a frase. Use o formato: `[NomeDoArquivo.pdf, Page: X]`. Se o parágrafo for baseado em múltiplas páginas, cite todas elas. Ex: `[doc1.pdf, Page: 2] [doc1.pdf, Page: 5]`.\n"
            "4. **Citações no Fim do Ponto**: Além das citações nas frases, ao final de cada um dos '5 pontos', adicione uma linha: '*Fontes: [Arquivo.pdf, Page: X]*'.\n"
            "\n"
            "- SOBRE O CONTEXTO: O contexto abaixo contém trechos marcados com 'Source:'. Use essa informação para as citações.\n"
            "- SE O CONTEXTO PARECER TOTALMENTE IRRELEVANTE para a pergunta, diga que não encontrou informações específicas. Porém, se o usuário pedir 'o que diz o documento' ou um 'resumo', tente resumir o que está no contexto de forma geral.\n"
        )

        if with_history:
            base_prompt += (
                "\n"
                "HISTÓRICO DA CONVERSA:\n"
                "- Você tem acesso ao histórico recente da conversa abaixo.\n"
                "- Use-o para entender o contexto e responder perguntas de acompanhamento como 'explique melhor', 'detalhe isso', etc.\n"
                "- Se a pergunta atual parecer uma continuação, considere o contexto anterior.\n"
                "\n"
                "Histórico:\n"
                "{history}\n"
            )

        base_prompt += "\nContexto dos Documentos:\n{context}"
        return base_prompt

    def _retrieve_and_rerank(
        self,
        question: str,
        doc_id: str = None,
        collection_id: str = None,
        k_initial: int = 40,
        k_final: int = 7
    ) -> List:
        """Retrieve documents and rerank them."""
        retriever = vector_store_service.as_retriever(
            doc_id=doc_id,
            collection_id=collection_id,
            k=k_initial,
            search_type="similarity"
        )

        initial_docs = retriever.invoke(question)
        logger.info(f"Retrieved {len(initial_docs)} initial docs for collection={collection_id}")

        if not initial_docs:
            logger.warning("No documents found for query")
            return []

        reranked_docs = []
        try:
            reranked_docs = rerank_service.rerank(question, initial_docs, top_k=k_final)
            logger.info(f"Reranked to top {len(reranked_docs)} documents")

            # Safety net for low scores
            if reranked_docs and reranked_docs[0].metadata.get("rerank_score", 0) <= 0.0001:
                logger.warning("Reranker scores too low, falling back to similarity results")
                reranked_docs = initial_docs[:k_final]

        except Exception as e:
            logger.error(f"Reranking failed: {e}", exc_info=True)
            reranked_docs = initial_docs[:k_final]

        if not reranked_docs and initial_docs:
            reranked_docs = initial_docs[:k_final]

        return reranked_docs

    def _format_history(self, chat_history: List[Dict]) -> str:
        """Format chat history for prompt inclusion."""
        if not chat_history:
            return "Nenhum histórico anterior."

        # Take last 5 exchanges max to avoid token overflow
        recent_history = chat_history[-10:]
        formatted = []

        for msg in recent_history:
            role = "Usuário" if msg.get("role") == "user" else "Assistente"
            content = msg.get("content", "")[:500]  # Truncate long messages
            formatted.append(f"{role}: {content}")

        return "\n".join(formatted)

    def get_answer(
        self,
        question: str,
        doc_id: str = None,
        collection_id: str = None,
        chat_history: Optional[List[Dict]] = None
    ) -> str:
        """
        Answers a question based on a specific document OR collection.
        Now supports conversation history for context.
        """
        logger.info(f"Processing question: '{question[:50]}...' (collection={collection_id})")

        # 1. Retrieve and rerank documents
        reranked_docs = self._retrieve_and_rerank(question, doc_id, collection_id)

        # 2. Build prompt with or without history
        has_history = bool(chat_history and len(chat_history) > 0)
        system_prompt = self._get_system_prompt(with_history=has_history)

        if has_history:
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "{input}"),
            ])
        else:
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "{input}"),
            ])

        # 3. Generate answer
        document_prompt = ChatPromptTemplate.from_template(
            "Source: {filename} (Page {page_number})\nContent: {page_content}"
        )
        question_answer_chain = create_stuff_documents_chain(
            self.llm, prompt, document_prompt=document_prompt
        )

        invoke_params = {
            "input": question,
            "context": reranked_docs
        }

        if has_history:
            invoke_params["history"] = self._format_history(chat_history)

        response = question_answer_chain.invoke(invoke_params)

        # Ensure we return a string
        if isinstance(response, dict):
            # Depends on version, sometimes returns 'answer' or 'output_text'
            response = response.get("answer") or response.get("output_text") or str(response)

        return response

    def stream_answer(
        self,
        question: str,
        doc_id: str = None,
        collection_id: str = None,
        chat_history: Optional[List[Dict]] = None
    ) -> Generator[str, None, None]:
        """
        Stream answer chunks for real-time response display.
        Yields text chunks as they are generated.
        """
        logger.info(f"Streaming answer for: '{question[:50]}...'")

        # 1. Retrieve and rerank documents
        reranked_docs = self._retrieve_and_rerank(question, doc_id, collection_id)

        if not reranked_docs:
            yield "Não encontrei documentos relevantes para responder sua pergunta."
            return

        # 2. Build context manually for streaming
        context_parts = []
        for doc in reranked_docs:
            filename = doc.metadata.get('filename', 'Unknown')
            page = doc.metadata.get('page_number', '?')
            content = doc.page_content
            context_parts.append(f"Source: {filename} (Page {page})\nContent: {content}")

        context = "\n\n---\n\n".join(context_parts)

        # 3. Build messages for streaming
        has_history = bool(chat_history and len(chat_history) > 0)
        system_prompt = self._get_system_prompt(with_history=has_history)

        if has_history:
            system_prompt = system_prompt.replace("{history}", self._format_history(chat_history))

        system_prompt = system_prompt.replace("{context}", context)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ]

        # 4. Stream response
        try:
            for chunk in self.streaming_llm.stream(messages):
                if chunk.content:
                    yield chunk.content
        except Exception as e:
            logger.error(f"Streaming error: {e}", exc_info=True)
            yield f"\n\n[Erro ao gerar resposta: {str(e)}]"

        logger.info("Streaming completed")

rag_service = RAGService()
