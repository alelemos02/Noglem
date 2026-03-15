"use client";

import { Suspense, useEffect, useState, useRef, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import {
  Mail,
  RefreshCw,
  MessageSquare,
  Link2,
  Unlink,
  Loader2,
  CheckCircle2,
  AlertCircle,
  ShieldCheck,
  Send,
  Bot,
  User,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  CardFooter,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

// --- Types ---

interface EmailAccount {
  id: string;
  email_address: string | null;
  display_name: string | null;
  status: string;
  collection_id: string | null;
  consent_accepted_at: string | null;
  created_at: string;
}

interface SyncJob {
  id: string;
  status: string;
  period_months: number;
  total_emails: number;
  processed_emails: number;
  indexed_emails: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

interface EmailStats {
  total_emails: number;
  indexed_emails: number;
  last_sync: string | null;
  collection_id: string | null;
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

// --- Page States ---

type PageState =
  | "loading"
  | "consent"
  | "disconnected"
  | "connected"
  | "syncing"
  | "ready";

// --- Component ---

export default function EmailDashboardPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-accent" />
        </div>
      }
    >
      <EmailDashboard />
    </Suspense>
  );
}

function EmailDashboard() {
  const searchParams = useSearchParams();

  const [pageState, setPageState] = useState<PageState>("loading");
  const [account, setAccount] = useState<EmailAccount | null>(null);
  const [stats, setStats] = useState<EmailStats | null>(null);
  const [syncJob, setSyncJob] = useState<SyncJob | null>(null);
  const [periodMonths, setPeriodMonths] = useState(3);
  const [error, setError] = useState<string | null>(null);
  const [consentChecked, setConsentChecked] = useState(false);

  // Chat state
  const [chatSessionId, setChatSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // --- Init ---

  useEffect(() => {
    const errorParam = searchParams.get("error");
    if (errorParam) {
      setError(
        errorParam === "callback_failed"
          ? "Falha na conexão com Microsoft. Tente novamente."
          : errorParam
      );
    }

    const connected = searchParams.get("connected");
    if (connected === "true") {
      setError(null);
    }

    loadAccountState();
  }, [searchParams]);

  const loadAccountState = async () => {
    try {
      const res = await fetch("/api/email/account");
      if (res.status === 404) {
        setPageState("consent");
        return;
      }
      if (!res.ok) throw new Error("Erro ao carregar conta");

      const data: EmailAccount = await res.json();
      setAccount(data);

      if (!data.consent_accepted_at) {
        setPageState("consent");
        return;
      }

      if (data.status === "disconnected" || data.status === "token_expired") {
        setPageState("disconnected");
        return;
      }

      // Conta conectada — verificar sync
      const statsRes = await fetch("/api/email/stats");
      if (statsRes.ok) {
        const statsData: EmailStats = await statsRes.json();
        setStats(statsData);

        if (statsData.indexed_emails > 0) {
          setPageState("ready");
          return;
        }
      }

      // Verificar se há sync em andamento
      try {
        const syncRes = await fetch("/api/email/sync/status");
        if (syncRes.ok) {
          const syncData: SyncJob = await syncRes.json();
          setSyncJob(syncData);
          if (syncData.status === "syncing") {
            setPageState("syncing");
            return;
          }
        }
      } catch {
        // Sem sync anterior — tudo bem
      }

      setPageState("connected");
    } catch {
      setPageState("consent");
    }
  };

  // --- Consent ---

  const handleConsent = async () => {
    try {
      await fetch("/api/email/consent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ accepted: true }),
      });
      setPageState("disconnected");
    } catch {
      setError("Erro ao registrar consentimento");
    }
  };

  // --- OAuth ---

  const handleConnect = async () => {
    try {
      const res = await fetch("/api/email/auth/url");
      if (!res.ok) throw new Error();
      const data: { auth_url: string } = await res.json();
      window.location.href = data.auth_url;
    } catch {
      setError("Erro ao gerar link de autenticação");
    }
  };

  const handleDisconnect = async () => {
    if (!confirm("Desconectar conta e apagar todos os emails indexados?")) return;
    try {
      await fetch("/api/email/account", { method: "DELETE" });
      setAccount(null);
      setStats(null);
      setSyncJob(null);
      setMessages([]);
      setChatSessionId(null);
      setPageState("disconnected");
    } catch {
      setError("Erro ao desconectar");
    }
  };

  // --- Sync ---

  const handleSync = async () => {
    setError(null);
    try {
      const res = await fetch("/api/email/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ period_months: periodMonths }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Erro ao iniciar sync");
      }
      const job: SyncJob = await res.json();
      setSyncJob(job);
      setPageState("syncing");
      pollSyncStatus();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao iniciar sync");
    }
  };

  const pollSyncStatus = useCallback(() => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch("/api/email/sync/status");
        if (!res.ok) return;
        const job: SyncJob = await res.json();
        setSyncJob(job);

        if (job.status === "completed" || job.status === "failed") {
          clearInterval(interval);
          if (job.status === "completed") {
            // Reload stats
            const statsRes = await fetch("/api/email/stats");
            if (statsRes.ok) setStats(await statsRes.json());
            setPageState("ready");
          } else {
            setError(job.error_message || "Sincronização falhou");
            setPageState("connected");
          }
        }
      } catch {
        clearInterval(interval);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  // --- Chat ---

  const ensureChatSession = async (): Promise<string> => {
    if (chatSessionId) return chatSessionId;
    const res = await fetch("/api/email/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (!res.ok) throw new Error("Erro ao criar sessão de chat");
    const data = await res.json();
    setChatSessionId(data.id);
    return data.id;
  };

  const handleSendMessage = async () => {
    if (!chatInput.trim() || isStreaming) return;

    const question = chatInput.trim();
    setChatInput("");

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: question,
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsStreaming(true);

    try {
      const sessionId = await ensureChatSession();

      const res = await fetch(`/api/email/chat/${sessionId}/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: question }),
      });

      if (!res.ok) throw new Error("Erro ao enviar mensagem");
      if (!res.body) throw new Error("Sem body na resposta");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();

      const assistantMsg: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: "",
      };
      setMessages((prev) => [...prev, assistantMsg]);

      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.chunk) {
              assistantMsg.content += data.chunk;
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMsg.id
                    ? { ...m, content: assistantMsg.content }
                    : m
                )
              );
            }
            if (data.done) {
              assistantMsg.id = data.message_id || assistantMsg.id;
            }
          } catch {
            // Ignorar linhas malformadas
          }
        }
      }
    } catch (e) {
      const errorMsg: ChatMessage = {
        id: `error-${Date.now()}`,
        role: "assistant",
        content: `Erro: ${e instanceof Error ? e.message : "Falha na comunicação"}`,
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsStreaming(false);
    }
  };

  // Auto-scroll chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // --- Render Helpers ---

  const renderConsent = () => (
    <Card className="max-w-2xl mx-auto animate-fade-in-up">
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent-muted">
            <ShieldCheck className="h-5 w-5 text-accent" />
          </div>
          <div>
            <CardTitle className="font-heading">Termos de Uso — Email RAG</CardTitle>
            <CardDescription>
              Leia antes de conectar sua conta Microsoft
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-lg bg-bg-secondary p-4 space-y-3 text-sm text-text-secondary">
          <p>
            <strong className="text-text-primary">1. Indexação local:</strong>{" "}
            Seus emails são processados e indexados usando um modelo de IA que
            roda localmente no servidor. Nenhum conteúdo de email é enviado para
            serviços externos durante a indexação.
          </p>
          <p>
            <strong className="text-text-primary">2. Consultas com IA:</strong>{" "}
            Ao fazer perguntas, trechos relevantes dos seus emails (5-7 trechos
            por consulta) são enviados ao modelo GPT-4o-mini da OpenAI para
            gerar a resposta.
          </p>
          <p>
            <strong className="text-text-primary">
              3. Tokens de acesso:
            </strong>{" "}
            Tokens de autenticação do Microsoft são armazenados no servidor para
            manter a conexão. Apenas permissão de leitura (Mail.Read) é
            solicitada.
          </p>
          <p>
            <strong className="text-text-primary">
              4. Controle total:
            </strong>{" "}
            Você pode desconectar sua conta e apagar todos os dados indexados a
            qualquer momento.
          </p>
        </div>
        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={consentChecked}
            onChange={(e) => setConsentChecked(e.target.checked)}
            className="mt-1 h-4 w-4 rounded border-border accent-accent"
          />
          <span className="text-sm text-text-secondary">
            Li e compreendo como meus dados de email serão processados.
          </span>
        </label>
      </CardContent>
      <CardFooter>
        <Button
          onClick={handleConsent}
          disabled={!consentChecked}
          className="w-full"
        >
          Prosseguir
        </Button>
      </CardFooter>
    </Card>
  );

  const renderDisconnected = () => (
    <Card className="max-w-lg mx-auto animate-fade-in-up">
      <CardHeader>
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-info-muted">
            <Mail className="h-5 w-5 text-info" />
          </div>
          <div>
            <CardTitle className="font-heading">Conectar Microsoft 365</CardTitle>
            <CardDescription>
              Vincule sua conta para indexar e consultar seus emails
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-text-secondary mb-4">
          Ao conectar, solicitaremos apenas permissão de leitura dos seus
          emails. Nenhum email será enviado ou modificado.
        </p>
        <Button onClick={handleConnect} className="w-full">
          <Link2 className="mr-2 h-4 w-4" />
          Conectar Microsoft 365
        </Button>
      </CardContent>
    </Card>
  );

  const renderConnected = () => (
    <div className="max-w-2xl mx-auto space-y-6 animate-fade-in-up">
      {/* Account info */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-success-muted">
                <CheckCircle2 className="h-5 w-5 text-success" />
              </div>
              <div>
                <CardTitle className="font-heading text-lg">
                  {account?.display_name || "Conta Conectada"}
                </CardTitle>
                <CardDescription>{account?.email_address}</CardDescription>
              </div>
            </div>
            <Button variant="ghost" size="sm" onClick={handleDisconnect}>
              <Unlink className="mr-2 h-3 w-3" />
              Desconectar
            </Button>
          </div>
        </CardHeader>
      </Card>

      {/* Sync controls */}
      <Card>
        <CardHeader>
          <CardTitle className="font-heading text-lg">Sincronizar Emails</CardTitle>
          <CardDescription>
            Selecione o período e inicie a sincronização
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-4 gap-2">
            {[
              { label: "1 mês", value: 1 },
              { label: "3 meses", value: 3 },
              { label: "6 meses", value: 6 },
              { label: "1 ano", value: 12 },
            ].map((opt) => (
              <button
                key={opt.value}
                onClick={() => setPeriodMonths(opt.value)}
                className={cn(
                  "rounded-lg border px-3 py-2 text-sm font-mono tabular-nums transition-colors",
                  periodMonths === opt.value
                    ? "border-accent bg-accent-muted text-accent"
                    : "border-border bg-surface text-text-secondary hover:bg-surface-hover"
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <Button onClick={handleSync} className="w-full">
            <RefreshCw className="mr-2 h-4 w-4" />
            Sincronizar Emails
          </Button>
        </CardContent>
      </Card>
    </div>
  );

  const renderSyncing = () => (
    <Card className="max-w-lg mx-auto animate-fade-in-up">
      <CardHeader>
        <div className="flex items-center gap-3">
          <Loader2 className="h-5 w-5 animate-spin text-accent" />
          <div>
            <CardTitle className="font-heading">Sincronizando Emails</CardTitle>
            <CardDescription>Isso pode levar alguns minutos...</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {syncJob && (
          <>
            <div className="w-full bg-bg-tertiary rounded-lg h-2 overflow-hidden">
              <div
                className="bg-accent h-full rounded-lg transition-all duration-500"
                style={{
                  width: `${syncJob.total_emails > 0 ? (syncJob.processed_emails / syncJob.total_emails) * 100 : 0}%`,
                }}
              />
            </div>
            <div className="flex justify-between text-sm text-text-secondary">
              <span>
                <span className="font-mono tabular-nums">
                  {syncJob.processed_emails}
                </span>{" "}
                /{" "}
                <span className="font-mono tabular-nums">
                  {syncJob.total_emails}
                </span>{" "}
                emails processados
              </span>
              <span>
                <span className="font-mono tabular-nums">
                  {syncJob.indexed_emails}
                </span>{" "}
                indexados
              </span>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );

  const renderReady = () => (
    <div className="flex flex-col h-full max-h-[calc(100vh-120px)] animate-fade-in-up">
      {/* Stats bar */}
      <div className="flex items-center justify-between pb-4 border-b border-border shrink-0">
        <div className="flex items-center gap-4">
          <Badge variant="success" dot>
            Conectado
          </Badge>
          <span className="text-sm text-text-secondary">
            {account?.email_address}
          </span>
          {stats && (
            <>
              <span className="text-sm text-text-tertiary">|</span>
              <span className="text-sm text-text-secondary">
                <span className="font-mono tabular-nums">
                  {stats.indexed_emails}
                </span>{" "}
                emails indexados
              </span>
              {stats.last_sync && (
                <>
                  <span className="text-sm text-text-tertiary">|</span>
                  <span className="text-sm text-text-tertiary">
                    Último sync:{" "}
                    {new Date(stats.last_sync).toLocaleDateString("pt-BR")}
                  </span>
                </>
              )}
            </>
          )}
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => setPageState("connected")}>
            <RefreshCw className="mr-2 h-3 w-3" />
            Re-sincronizar
          </Button>
          <Button variant="ghost" size="sm" onClick={handleDisconnect}>
            <Unlink className="h-3 w-3" />
          </Button>
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto py-4 space-y-4 min-h-0">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-lg bg-accent-muted mb-4">
              <MessageSquare className="h-8 w-8 text-accent" />
            </div>
            <h3 className="text-lg font-heading font-semibold text-text-primary">
              Consulte seus emails com IA
            </h3>
            <p className="text-sm text-text-secondary max-w-md mt-2">
              Faça perguntas sobre qualquer assunto dos seus emails. A IA
              buscará nos emails indexados e responderá com citações.
            </p>
            <div className="mt-6 flex flex-wrap gap-2 max-w-lg justify-center">
              {[
                "Quais emails recebi sobre o projeto X?",
                "Resuma as últimas comunicações com o fornecedor Y",
                "Quem me enviou emails sobre a reunião de kick-off?",
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => setChatInput(suggestion)}
                  className="text-xs px-3 py-1.5 rounded-lg border border-border bg-surface hover:bg-surface-hover text-text-secondary transition-colors"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={cn(
              "flex gap-3 max-w-3xl",
              msg.role === "user" ? "ml-auto flex-row-reverse" : ""
            )}
          >
            <div
              className={cn(
                "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
                msg.role === "user"
                  ? "bg-accent-muted"
                  : "bg-info-muted"
              )}
            >
              {msg.role === "user" ? (
                <User className="h-4 w-4 text-accent" />
              ) : (
                <Bot className="h-4 w-4 text-info" />
              )}
            </div>
            <div
              className={cn(
                "rounded-lg px-4 py-3 text-sm leading-relaxed",
                msg.role === "user"
                  ? "bg-accent-muted text-text-primary"
                  : "bg-surface text-text-primary"
              )}
            >
              <div className="whitespace-pre-wrap">{msg.content}</div>
              {msg.role === "assistant" &&
                isStreaming &&
                msg.id === messages[messages.length - 1]?.id && (
                  <span className="inline-block w-1.5 h-4 bg-accent ml-0.5 animate-pulse" />
                )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Chat input */}
      <div className="border-t border-border pt-4 shrink-0">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSendMessage();
          }}
          className="flex gap-2"
        >
          <Input
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            placeholder="Pergunte algo sobre seus emails..."
            disabled={isStreaming}
            className="flex-1"
          />
          <Button type="submit" disabled={!chatInput.trim() || isStreaming} size="icon">
            {isStreaming ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </form>
      </div>
    </div>
  );

  // --- Main Render ---

  return (
    <div className="flex flex-col h-full p-8">
      {/* Header */}
      <div className="mb-8 shrink-0">
        <h1 className="text-3xl font-bold tracking-tight font-heading">
          Email RAG
        </h1>
        <p className="text-text-secondary mt-2">
          Conecte seu Microsoft 365 e consulte seus emails usando IA.
        </p>
      </div>

      {/* Error banner */}
      {error && (
        <div className="mb-6 flex items-center gap-2 rounded-lg bg-error-muted p-3 text-sm text-error shrink-0">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
          <button
            onClick={() => setError(null)}
            className="ml-auto text-error hover:text-error/80"
          >
            Fechar
          </button>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 min-h-0">
        {pageState === "loading" && (
          <div className="flex h-64 items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-accent" />
          </div>
        )}
        {pageState === "consent" && renderConsent()}
        {pageState === "disconnected" && renderDisconnected()}
        {pageState === "connected" && renderConnected()}
        {pageState === "syncing" && renderSyncing()}
        {pageState === "ready" && renderReady()}
      </div>
    </div>
  );
}
