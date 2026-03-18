"use client";

import { useState, useRef, useEffect, use } from "react";
import { MessageSquare, Send, Upload, FileText, Trash2, ArrowLeft, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useRouter } from "next/navigation";

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
    const router = useRouter();
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
                } else {
                    const errorBody = await res.json().catch(() => ({ detail: "Erro ao enviar arquivo" }));
                    console.error("Upload failed:", res.status, errorBody);
                    const detail = errorBody?.detail;
                    const errorMsg = typeof detail === "string"
                        ? detail
                        : detail ? JSON.stringify(detail) : `HTTP ${res.status}`;
                    alert(`Erro ao enviar ${file.name}: ${errorMsg}`);
                }
            }
        } catch (error) {
            console.error("Erro no upload:", error);
        } finally {
            setIsUploading(false);
            // Reset the input so the same file can be uploaded again
            e.target.value = "";
        }
    };

    const handleRemoveDocument = async (doc: BackendDocument) => {
        try {
            const res = await fetch(`/api/rag/collections/${collectionId}/documents/${doc.id}`, {
                method: "DELETE",
            });

            if (res.ok || res.status === 204) {
                setDocuments((prev) => prev.filter((d) => d.id !== doc.id));
            } else {
                console.error("Erro ao remover documento");
            }
        } catch (error) {
            console.error("Erro ao remover documento:", error);
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
        <div className="flex h-[calc(100vh-8rem)] flex-col space-y-4">
            {/* Header */}
            <div className="flex items-center gap-4">
                <Button variant="ghost" size="icon" onClick={() => router.back()}>
                    <ArrowLeft className="h-5 w-5" />
                </Button>
                <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
                    <MessageSquare className="h-6 w-6 text-primary" />
                </div>
                <div>
                    <h1 className="text-2xl font-bold font-heading">Workspace: {collectionName}</h1>
                    <p className="text-muted-foreground">
                        Adicione documentos a esta coleção para começar.
                    </p>
                </div>
            </div>

            <div className="flex flex-1 gap-4 overflow-hidden">
                {/* Documents Sidebar */}
                <Card className="w-64 flex-shrink-0 flex flex-col">
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base">Documentos Ativos</CardTitle>
                    </CardHeader>
                    <CardContent className="flex-1 overflow-hidden flex flex-col space-y-4">
                        <label className={`flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed border-muted-foreground/25 p-4 transition-colors hover:border-primary/50 hover:bg-muted/50 ${isUploading ? "pointer-events-none opacity-50" : ""}`}>
                            {isUploading ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                                <Upload className="h-4 w-4" />
                            )}
                            <span className="text-sm">{isUploading ? "Enviando..." : "Adicionar PDF"}</span>
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
                            <div className="space-y-2 pr-4">
                                {documents.length === 0 ? (
                                    <p className="text-center text-sm text-muted-foreground py-8">
                                        Nenhum documento nesta coleção.
                                    </p>
                                ) : (
                                    documents.map((doc) => (
                                        <div
                                            key={doc.id}
                                            className="flex items-center gap-2 rounded-lg bg-muted p-2 group"
                                        >
                                            <FileText className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                                            <div className="flex-1 min-w-0">
                                                <span className="block truncate text-sm">{doc.filename}</span>
                                                {doc.status === "processing" && (
                                                    <span className="text-[10px] text-warning">Processando...</span>
                                                )}
                                                {doc.status === "failed" && (
                                                    <span className="text-[10px] text-error" title={doc.error_message || "Erro desconhecido"}>
                                                        Falhou {doc.error_message ? "⚠" : ""}
                                                    </span>
                                                )}
                                            </div>
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                                                onClick={() => handleRemoveDocument(doc)}
                                            >
                                                <Trash2 className="h-3 w-3 text-destructive" />
                                            </Button>
                                        </div>
                                    ))
                                )}
                            </div>
                        </ScrollArea>
                    </CardContent>
                </Card>

                {/* Chat Area */}
                <Card className="flex flex-1 flex-col overflow-hidden">
                    <CardContent className="flex flex-1 flex-col p-0">
                        {/* Messages */}
                        <ScrollArea className="flex-1 p-4">
                            <div className="space-y-6 max-w-3xl mx-auto">
                                {messages.length === 0 ? (
                                    <div className="flex h-full flex-col items-center justify-center py-20 text-center opacity-50">
                                        <MessageSquare className="h-16 w-16 mb-4" />
                                        <h3 className="text-lg font-medium font-heading">Chat Vazio</h3>
                                        <p>Carregue um PDF ao lado e comece a perguntar.</p>
                                    </div>
                                ) : (
                                    messages.map((message) => (
                                        <div
                                            key={message.id}
                                            className={`flex gap-3 ${message.role === "user" ? "flex-row-reverse" : "flex-row"
                                                }`}
                                        >
                                            {/* Avatar */}
                                            <div className={`
                         h-8 w-8 rounded-full flex items-center justify-center text-xs font-bold
                         ${message.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted-foreground/20 text-foreground'}
                      `}>
                                                {message.role === 'user' ? 'VC' : 'IA'}
                                            </div>

                                            {/* Bubble */}
                                            <div
                                                className={`max-w-[80%] rounded-2xl px-4 py-3 shadow-sm ${message.role === "user"
                                                        ? "bg-primary text-primary-foreground rounded-tr-sm"
                                                        : "bg-muted/50 rounded-tl-sm border"
                                                    }`}
                                            >
                                                <p className="whitespace-pre-wrap text-sm leading-relaxed">
                                                    {message.content}
                                                </p>
                                                {message.sources && message.sources.length > 0 && (
                                                    <div className="mt-3 flex flex-wrap gap-2 pt-2 border-t border-border/10">
                                                        {message.sources.map((src, i) => (
                                                            <Badge key={i} variant="outline" className="text-[10px] h-5 bg-background/50">
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
                                        <div className="h-8 w-8 rounded-full bg-muted-foreground/20 flex items-center justify-center text-xs">IA</div>
                                        <div className="bg-muted/50 rounded-2xl rounded-tl-sm px-4 py-3 border flex items-center gap-1">
                                            <span className="w-1.5 h-1.5 bg-primary/60 rounded-full animate-bounce [animation-delay:-0.3s]"></span>
                                            <span className="w-1.5 h-1.5 bg-primary/60 rounded-full animate-bounce [animation-delay:-0.15s]"></span>
                                            <span className="w-1.5 h-1.5 bg-primary/60 rounded-full animate-bounce"></span>
                                        </div>
                                    </div>
                                )}
                                <div ref={messagesEndRef} />
                            </div>
                        </ScrollArea>

                        {/* Input */}
                        <div className="p-4 border-t bg-background/50 backdrop-blur-sm">
                            <div className="max-w-3xl mx-auto flex gap-2 relative">
                                <input
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
                                    className="flex-1 rounded-full border border-input bg-background/80 px-6 py-3 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-ring transition-all pr-12"
                                    disabled={isLoading}
                                />
                                <Button
                                    onClick={handleSend}
                                    disabled={!input.trim() || isLoading}
                                    size="icon"
                                    className="absolute right-1.5 top-1.5 rounded-full h-9 w-9"
                                >
                                    <Send className="h-4 w-4" />
                                </Button>
                            </div>
                            <div className="text-center mt-2 text-[10px] text-muted-foreground">
                                O RAG pode cometer erros. Verifique as fontes.
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
