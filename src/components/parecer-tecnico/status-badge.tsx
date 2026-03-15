"use client";

const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  A: { label: "A - Aprovado", className: "bg-green-900/40 text-green-400 border-green-700/50" },
  B: { label: "B - Aprov. Com.", className: "bg-yellow-900/40 text-yellow-400 border-yellow-700/50" },
  C: { label: "C - Rejeitado", className: "bg-red-900/40 text-red-400 border-red-700/50" },
  D: { label: "D - Info Ausente", className: "bg-gray-800/60 text-gray-400 border-gray-600/50" },
  E: { label: "E - Adicional", className: "bg-blue-900/40 text-blue-400 border-blue-700/50" },
};

const PARECER_GERAL_CONFIG: Record<string, { label: string; className: string }> = {
  APROVADO: { label: "Aprovado", className: "bg-green-900/40 text-green-400 border-green-700/50" },
  APROVADO_COM_COMENTARIOS: { label: "Aprov. c/ Com.", className: "bg-yellow-900/40 text-yellow-400 border-yellow-700/50" },
  REJEITADO: { label: "Rejeitado", className: "bg-red-900/40 text-red-400 border-red-700/50" },
};

const PROCESSAMENTO_CONFIG: Record<string, { label: string; className: string }> = {
  pendente: { label: "Pendente", className: "bg-gray-800/60 text-gray-400 border-gray-600/50" },
  processando: { label: "Processando", className: "bg-blue-900/40 text-blue-400 border-blue-700/50" },
  concluido: { label: "Concluído", className: "bg-green-900/40 text-green-400 border-green-700/50" },
  erro: { label: "Erro", className: "bg-red-900/40 text-red-400 border-red-700/50" },
};

function BaseBadge({ config, value }: { config: Record<string, { label: string; className: string }>; value: string | null }) {
  if (!value) return null;
  const c = config[value];
  if (!c) return <span className="inline-flex items-center rounded-md border border-border px-2 py-0.5 text-xs font-medium text-text-tertiary">{value}</span>;
  return <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${c.className}`}>{c.label}</span>;
}

export function StatusBadge({ status }: { status: string }) {
  return <BaseBadge config={STATUS_CONFIG} value={status} />;
}

export function ParecerGeralBadge({ status }: { status: string | null }) {
  return <BaseBadge config={PARECER_GERAL_CONFIG} value={status} />;
}

export function ProcessamentoBadge({ status }: { status: string }) {
  return <BaseBadge config={PROCESSAMENTO_CONFIG} value={status} />;
}
