"use client";

import { useState, useRef, useEffect, use } from "react";
import { MessageSquare, Send, Upload, FileText, Trash2, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { PageHeader } from "@/components/ui/page-header";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toast";
import { useConfirm } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";

interface Message {
    id: string;
    role: "user" | "assistant";
    content: string;
    sources?: string[];
}

interface BackendDocument {
    id: string;
    collection_id: string;
    filename: string;
    status: "uploaded" | "processing" | "ready" | "failed";
    has_ocr: boolean;
    error_message?: string | null;
    created_at: string;
}

interface CollectionData {
    id: string;
    name: string;
    created_at: string;
    documents: BackendDocument[];
}

export default function RagCollectionPage({ params }: { params: Promise<{ collectionId: string }> }) {
    const { collectionId } = use(params);
    const confirm = useConfirm();
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [collection, setCollection] = useState<CollectionData | null>(null);
    const [documents, setDocuments] = useState<BackendDocument[]>([]);
    const [isUploading, setIsUploading] = useState(false);
    const [chatId, setChatId] = useState<string | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    // Load collection and documents on mount
    useEffect(() => {
        async function loadCollection() {
            try {
                const res = await fetch(`/api/rag/collections/${collectionId}`);
                if (res.ok) {
                    const data: CollectionData = await res.json();
                    setCollection(data);
                    setDocuments(data.documents || []);
                }
            } catch (error) {
                console.error("Erro ao carregar coleção:", error);
            }
        }
        loadCollection();
    }, [collectionId]);

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (!files || files.length === 0) return;

        setIsUploading(true);
        try {
            for (const file of Array.from(files)) {
                const formData = new FormData();
                formData.append("file", file);

                const res = await fetch(`/api/rag/collections/${collectionId}/documents`, {
                    method: "POST",
                    body: formData,
                });

                if (res.ok) {
                    const newDoc: BackendDocument = await res.json();
                    setDocuments((prev) => [...prev, newDoc]);
                    toast.success("Documento enviado", { description: file.name });
                } else {
                    const errorBody = await res.json().catch(() => ({ detail: "Erro ao enviar arquivo" }));
                    console.error("Upload failed:", res.status, errorBody);
                    const detail = errorBody?.detail;
                    const errorMsg = typeof detail === "string"
                        ? detail
                        : detail ? JSON.stringify(detail) : `HTTP ${res.status}`;
                    toast.error(`Erro ao enviar ${file.name}`, { description: errorMsg });
                }
            }
        } catch (error) {
            console.error("Erro no upload:", error);
            toast.error("Erro de comunicação no upload");
        } finally {
            setIsUploading(false);
            // Reset the input so the same file can be uploaded again
            e.target.value = "";
        }
    };

    const handleRemoveDocument = async (doc: BackendDocument) => {
        const ok = await confirm({
            title: "Remover documento?",
            description: `"${doc.filename}" será removido da coleção.`,
            confirmLabel: "Remover",
            variant: "danger",
        });
        if (!ok) return;

        try {
            const res = await fetch(`/api/rag/collections/${collectionId}/documents/${doc.id}`, {
                method: "DELETE",
            });

            if (res.ok || res.status === 204) {
                setDocuments((prev) => prev.filter((d) => d.id !== doc.id));
                toast.success("Documento removido");
            } else {
                toast.error("Erro ao remover documento");
            }
        } catch (error) {
            console.error("Erro ao remover documento:", error);
            toast.error("Erro ao remover documento");
        }
    };

    const ensureChatSession = async (): Promise<string | null> => {
        if (chatId) return chatId;

        try {
            const res = await fetch("/api/rag/chats", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ collection_id: collectionId }),
            });

            if (res.ok) {
                const session = await res.json();
                setChatId(session.id);
                return session.id;
            }
            console.error("Erro ao criar sessão de chat");
            return null;
        } catch (error) {
            console.error("Erro ao criar sessão de chat:", error);
            return null;
        }
    };

    const handleSend = async () => {
        if (!input.trim()) return;

        const userMessage: Message = {
            id: Date.now().toString(),
            role: "user",
            content: input,
        };

        setMessages((prev) => [...prev, userMessage]);
        const currentInput = input;
        setInput("");
        setIsLoading(true);

        try {
            const sessionId = await ensureChatSession();
            if (!sessionId) {
                setMessages((prev) => [
                    ...prev,
                    {
                        id: (Date.now() + 1).toString(),
                        role: "assistant",
                        content: "Erro: não foi possível criar a sessão de chat. Tente novamente.",
                    },
                ]);
                return;
            }

            const res = await fetch(`/api/rag/chats/${sessionId}/messages`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ role: "user", content: currentInput }),
            });

            if (res.ok) {
                const aiMsg = await res.json();
                const assistantMessage: Message = {
                    id: aiMsg.id,
                    role: "assistant",
                    content: aiMsg.content,
                    sources: documents
                        .filter((d) => d.status === "ready")
                        .map((d) => d.filename),
                };
                setMessages((prev) => [...prev, assistantMessage]);
            } else {
                const error = await res.json().catch(() => ({ detail: "Erro desconhecido" }));
                setMessages((prev) => [
                    ...prev,
                    {
                        id: (Date.now() + 1).toString(),
                        role: "assistant",
                        content: `Erro ao processar sua pergunta: ${error.detail || "Tente novamente."}`,
                    },
                ]);
            }
        } catch (error) {
            console.error("Erro ao enviar mensagem:", error);
            setMessages((prev) => [
                ...prev,
                {
                    id: (Date.now() + 1).toString(),
                    role: "assistant",
                    content: "Erro de comunicação com o servidor. Verifique sua conexão.",
                },
            ]);
        } finally {
            setIsLoading(false);
        }
    };

    const collectionName = collection?.name || collectionId;

    return (
        <div className="flex h-[calc(100vh-8rem)] flex-col">
            <PageHeader
                title={collectionName}
                description="Converse com os documentos desta coleção."
                backHref="/dashboard/rag"
                backLabel="Coleções"
                className="mb-4"
            />

            <div className="flex flex-1 gap-4 overflow-hidden">
                {/* Documents Sidebar */}
                <Card className="flex w-64 flex-shrink-0 flex-col gap-3 py-4">
                    <CardHeader>
                        <CardTitle className="text-sm">Documentos ativos</CardTitle>
                    </CardHeader>
                    <CardContent className="flex flex-1 flex-col space-y-4 overflow-hidden px-4">
                        <label className={`flex cursor-pointer items-center justify-center gap-2 rounded-md border border-dashed border-edge-strong p-3.5 text-fg-muted transition-colors hover:border-fg-subtle hover:text-fg ${isUploading ? "pointer-events-none opacity-50" : ""}`}>
                            {isUploading ? (
                                <Spinner size="xs" />
                            ) : (
                                <Upload className="h-4 w-4" />
                            )}
                            <span className="text-[13px] font-medium">{isUploading ? "Enviando..." : "Adicionar PDF"}</span>
                            <input
                                type="file"
                                accept=".pdf"
                                multiple
                                onChange={handleFileUpload}
                                className="hidden"
                                disabled={isUploading}
                            />
                        </label>

                        <ScrollArea className="flex-1">
                            <div className="space-y-1.5 pr-3">
                                {documents.length === 0 ? (
                                    <p className="py-8 text-center text-[13px] text-fg-subtle">
                                        Nenhum documento nesta coleção.
                                    </p>
                                ) : (
                                    documents.map((doc) => (
                                        <div
                                            key={doc.id}
                                            className="group flex items-center gap-2 rounded-md border border-edge bg-surface-2 px-2.5 py-2"
                                        >
                                            <FileText className="h-4 w-4 flex-shrink-0 text-fg-subtle" />
                                            <div className="min-w-0 flex-1">
                                                <span className="block truncate text-[13px] text-fg">{doc.filename}</span>
                                                {doc.status === "processing" && (
                                                    <span className="font-mono text-[10px] uppercase tracking-wide text-warning">Processando...</span>
                                                )}
                                                {doc.status === "failed" && (
                                                    <span className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-wide text-danger" title={doc.error_message || "Erro desconhecido"}>
                                                        <AlertTriangle className="h-3 w-3" /> Falhou
                                                    </span>
                                                )}
                                            </div>
                                            <Button
                                                variant="ghost"
                                                size="icon-xs"
                                                className="opacity-0 transition-opacity hover:bg-danger-subtle hover:text-danger group-hover:opacity-100"
                                                onClick={() => handleRemoveDocument(doc)}
                                                title="Remover documento"
                                            >
                                                <Trash2 className="h-3 w-3" />
                                            </Button>
                                        </div>
                                    ))
                                )}
                            </div>
                        </ScrollArea>
                    </CardContent>
                </Card>

                {/* Chat Area */}
                <Card className="flex flex-1 flex-col gap-0 overflow-hidden py-0">
                    <CardContent className="flex flex-1 flex-col overflow-hidden p-0">
                        {/* Messages */}
                        <ScrollArea className="min-h-0 flex-1 p-4">
                            <div className="mx-auto max-w-3xl space-y-5">
                                {messages.length === 0 ? (
                                    <div className="flex h-full flex-col items-center justify-center py-20 text-center">
                                        <MessageSquare className="mb-3 h-8 w-8 text-fg-subtle" />
                                        <h3 className="text-sm font-semibold text-fg">Comece uma conversa</h3>
                                        <p className="mt-1 text-[13px] text-fg-muted">Carregue um PDF ao lado e faça uma pergunta.</p>
                                    </div>
                                ) : (
                                    messages.map((message) => (
                                        <div
                                            key={message.id}
                                            className={`flex gap-3 ${message.role === "user" ? "flex-row-reverse" : "flex-row"}`}
                                        >
                                            {/* Avatar */}
                                            <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md border font-mono text-[10px] font-medium ${
                                                message.role === "user"
                                                    ? "border-accent/40 bg-accent-subtle text-accent"
                                                    : "border-edge-strong bg-surface-3 text-fg-muted"
                                            }`}>
                                                {message.role === "user" ? "VC" : "IA"}
                                            </div>

                                            {/* Bubble */}
                                            <div
                                                className={`max-w-[80%] rounded-lg px-4 py-3 ${
                                                    message.role === "user"
                                                        ? "border border-accent/25 bg-accent-subtle"
                                                        : "border border-edge bg-surface-2"
                                                }`}
                                            >
                                                <p className="whitespace-pre-wrap text-sm leading-relaxed text-fg">
                                                    {message.content}
                                                </p>
                                                {message.sources && message.sources.length > 0 && (
                                                    <div className="mt-3 flex flex-wrap gap-1.5 border-t border-edge pt-2">
                                                        {message.sources.map((src, i) => (
                                                            <Badge key={i} variant="outline" className="px-1.5 py-0 text-[9px]">
                                                                {src}
                                                            </Badge>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    ))
                                )}
                                {isLoading && (
                                    <div className="flex gap-3">
                                        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-edge-strong bg-surface-3 font-mono text-[10px] text-fg-muted">IA</div>
                                        <div className="flex items-center gap-2 rounded-lg border border-edge bg-surface-2 px-4 py-3">
                                            <Spinner size="xs" className="text-accent" />
                                            <span className="text-[13px] text-fg-muted">Consultando documentos...</span>
                                        </div>
                                    </div>
                                )}
                                <div ref={messagesEndRef} />
                            </div>
                        </ScrollArea>

                        {/* Input */}
                        <div className="border-t border-edge bg-surface-1 p-4">
                            <div className="relative mx-auto flex max-w-3xl gap-2">
                                <Input
                                    type="text"
                                    value={input}
                                    onChange={(e) => setInput(e.target.value)}
                                    onKeyDown={(e) => {
                                        if (e.key === "Enter" && !e.shiftKey) {
                                            e.preventDefault();
                                            handleSend();
                                        }
                                    }}
                                    autoFocus
                                    placeholder="Faça uma pergunta..."
                                    className="h-11 pr-12"
                                    disabled={isLoading}
                                />
                                <Button
                                    onClick={handleSend}
                                    disabled={!input.trim() || isLoading}
                                    size="icon"
                                    className="absolute right-1 top-1"
                                    title="Enviar"
                                >
                                    <Send className="h-4 w-4" />
                                </Button>
                            </div>
                            <div className="mt-2 text-center font-mono text-[10px] uppercase tracking-wide text-fg-subtle">
                                O RAG pode cometer erros — verifique as fontes.
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
