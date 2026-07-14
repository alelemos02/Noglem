"use client";

/**
 * CaseSidebar — trilha lateral de ações do caso (dentro da conversa).
 *
 * Torna clicáveis as ações que antes só existiam como comandos de texto:
 * ver a tabela/itens/rastreabilidade, ver requisitos e documentos, e exportar.
 * Cada botão apenas religa um handler que já existe no ConversationProvider —
 * nada de backend novo. Escondida no mobile (md:flex); lá os comandos seguem valendo.
 */

import { useState } from "react";
import {
  Table2,
  ListChecks,
  GitBranch,
  FileSearch,
  FileText,
  FileDown,
  FileSpreadsheet,
  FileType,
  Mail,
} from "lucide-react";
import { useConversation } from "./conversation-provider";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogBody,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const TIPO_LABEL: Record<string, string> = {
  engenharia: "Engenharia",
  fornecedor: "Fornecedor",
  anexo_engenharia: "Anexo",
};

function formatBytes(bytes: number | null): string {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function NavButton({
  icon: Icon,
  label,
  count,
  onClick,
  disabled,
}: {
  icon: typeof Table2;
  label: string;
  count?: number;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px] leading-tight transition-colors",
        disabled
          ? "cursor-default text-fg-disabled"
          : "text-fg-muted hover:bg-surface-2/60 hover:text-fg"
      )}
    >
      <Icon className="h-4 w-4 shrink-0" />
      <span className="flex-1 truncate text-left">{label}</span>
      {typeof count === "number" && count > 0 && (
        <span className="font-mono text-[10px] tabular-nums text-fg-disabled">
          {count}
        </span>
      )}
    </button>
  );
}

export function CaseSidebar() {
  const {
    snapshot,
    setShowDataPanel,
    pushEphemeral,
    exportar,
    downloadCarta,
  } = useConversation();
  const [panel, setPanel] = useState<null | "docs" | "requisitos">(null);

  const itens = snapshot?.itens ?? [];
  const documentos = snapshot?.documentos ?? [];
  const requisitos = snapshot?.requisitos ?? [];
  const temItens = itens.length > 0;

  const abrirWidget = (widget: "items-browser" | "rastreabilidade") => {
    pushEphemeral({
      kind: "widget",
      key: `nav-${widget}-${Date.now()}`,
      at: new Date().toISOString(),
      widget,
    });
  };

  return (
    <>
      <aside className="hidden w-52 shrink-0 flex-col border-r border-edge bg-surface-1 md:flex">
        <div className="flex flex-col gap-0.5 px-3 py-4">
          <div className="mb-1 px-2.5">
            <span className="microlabel text-[10px]">Ver</span>
          </div>
          <NavButton
            icon={Table2}
            label="Tabela do caso"
            count={itens.length}
            onClick={() => setShowDataPanel(true)}
            disabled={!temItens}
          />
          <NavButton
            icon={ListChecks}
            label="Itens"
            count={itens.length}
            onClick={() => abrirWidget("items-browser")}
            disabled={!temItens}
          />
          <NavButton
            icon={GitBranch}
            label="Rastreabilidade"
            onClick={() => abrirWidget("rastreabilidade")}
            disabled={!temItens}
          />
          <NavButton
            icon={FileSearch}
            label="Requisitos"
            count={requisitos.length}
            onClick={() => setPanel("requisitos")}
            disabled={requisitos.length === 0}
          />
          <NavButton
            icon={FileText}
            label="Documentos"
            count={documentos.length}
            onClick={() => setPanel("docs")}
            disabled={documentos.length === 0}
          />

          <div className="mb-1 mt-4 px-2.5">
            <span className="microlabel text-[10px]">Exportar</span>
          </div>
          <NavButton
            icon={FileDown}
            label="PDF"
            onClick={() => exportar("pdf")}
            disabled={!temItens}
          />
          <NavButton
            icon={FileSpreadsheet}
            label="Excel"
            onClick={() => exportar("xlsx")}
            disabled={!temItens}
          />
          <NavButton
            icon={FileType}
            label="Word"
            onClick={() => exportar("docx")}
            disabled={!temItens}
          />
          <NavButton
            icon={Mail}
            label="Carta de pendências"
            onClick={() => downloadCarta()}
            disabled={!temItens}
          />
        </div>
      </aside>

      {/* Painel de Documentos / Requisitos (modal leve, lê o snapshot) */}
      <Dialog open={panel !== null} onOpenChange={(v) => !v && setPanel(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {panel === "docs" ? "Documentos carregados" : "Requisitos extraídos"}
            </DialogTitle>
            <DialogDescription>
              {panel === "docs"
                ? "Arquivos que alimentam a análise deste caso."
                : "A lista de requisitos aprovada que serviu de base para a análise."}
            </DialogDescription>
          </DialogHeader>
          <DialogBody>
            {panel === "docs" && (
              <ul className="flex flex-col divide-y divide-edge">
                {documentos.map((d) => (
                  <li key={d.id} className="flex items-center gap-3 py-2.5">
                    <FileText className="h-4 w-4 shrink-0 text-fg-subtle" />
                    <span className="min-w-0 flex-1 truncate text-[13px] text-fg">
                      {d.nome_arquivo}
                    </span>
                    <Badge variant="secondary">
                      {TIPO_LABEL[d.tipo] ?? d.tipo}
                    </Badge>
                    <span className="w-16 shrink-0 text-right font-mono text-[11px] tabular-nums text-fg-subtle">
                      {formatBytes(d.tamanho_bytes)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            {panel === "requisitos" && (
              <ul className="flex flex-col divide-y divide-edge">
                {requisitos.map((r) => (
                  <li key={r.id} className="flex gap-3 py-2.5">
                    <span className="shrink-0 font-mono text-[11px] tabular-nums text-fg-subtle">
                      {String(r.numero).padStart(2, "0")}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-[13px] text-fg">{r.descricao_requisito}</p>
                      {r.valor_requerido && (
                        <p className="mt-0.5 font-mono text-[11px] text-fg-subtle">
                          {r.valor_requerido}
                        </p>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </DialogBody>
        </DialogContent>
      </Dialog>
    </>
  );
}
