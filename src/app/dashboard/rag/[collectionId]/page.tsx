"use client";

import { useState, useRef, useEffect } from "react";
import { MessageSquare, Send, Upload, FileText, Trash2, ArrowLeft } from "lucide-react";
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

export default function RagCollectionPage({ params }: { params: { collectionId: string } }) {
    const router = useRouter();
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [documents, setDocuments] = useState<string[]>([]);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const { collectionId } = params;

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (files) {
            const newDocs = Array.from(files).map((f) => f.name);
            setDocuments((prev) => [...prev, ...newDocs]);
            // TODO: Implement real upload to collectionId
        }
    };

    const handleRemoveDocument = (index: number) => {
        setDocuments((prev) => prev.filter((_, i) => i !== index));
        // TODO: Implement real delete
    };

    const handleSend = async () => {
        if (!input.trim()) return;

        const userMessage: Message = {
            id: Date.now().toString(),
            role: "user",
            content: input,
        };

        setMessages((prev) => [...prev, userMessage]);
        setInput("");
        setIsLoading(true);

        try {
            // TODO: Connect to Real RAG API
            // POST /api/rag/chats/{chatId}/messages
            await new Promise((resolve) => setTimeout(resolve, 1500));

            const assistantMessage: Message = {
                id: (Date.now() + 1).toString(),
                role: "assistant",
                content: `Resposta simulada para a coleção ${collectionId}.\n\nEm breve estarei conectado ao backend real!`,
                sources: documents.length > 0 ? [documents[0]] : undefined,
            };

            setMessages((prev) => [...prev, assistantMessage]);
        } catch (error) {
            console.error("Erro ao enviar mensagem:", error);
        } finally {
            setIsLoading(false);
        }
    };

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
                    <h1 className="text-2xl font-bold">Workspace: {collectionId}</h1>
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
                        <label className="flex cursor-pointer items-center justify-center gap-2 rounded-lg border border-dashed border-muted-foreground/25 p-4 transition-colors hover:border-primary/50 hover:bg-muted/50">
                            <Upload className="h-4 w-4" />
                            <span className="text-sm">Adicionar PDF</span>
                            <input
                                type="file"
                                accept=".pdf"
                                multiple
                                onChange={handleFileUpload}
                                className="hidden"
                            />
                        </label>

                        <ScrollArea className="flex-1">
                            <div className="space-y-2 pr-4">
                                {documents.length === 0 ? (
                                    <p className="text-center text-sm text-muted-foreground py-8">
                                        Nenhum documento nesta coleção.
                                    </p>
                                ) : (
                                    documents.map((doc, index) => (
                                        <div
                                            key={index}
                                            className="flex items-center gap-2 rounded-lg bg-muted p-2 group"
                                        >
                                            <FileText className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                                            <span className="flex-1 truncate text-sm">{doc}</span>
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                                                onClick={() => handleRemoveDocument(index)}
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
                                        <h3 className="text-lg font-medium">Chat Vazio</h3>
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
