"use client";

import { Badge, type BadgeProps } from "@/components/ui/badge";

type Variant = NonNullable<BadgeProps["variant"]>;

const STATUS_CONFIG: Record<string, { label: string; variant: Variant }> = {
  A: { label: "A · Aprovado", variant: "success" },
  B: { label: "B · Aprov. Com.", variant: "warning" },
  C: { label: "C · Rejeitado", variant: "error" },
  D: { label: "D · Info Ausente", variant: "secondary" },
  E: { label: "E · Adicional", variant: "info" },
};

const PARECER_GERAL_CONFIG: Record<string, { label: string; variant: Variant }> = {
  APROVADO: { label: "Aprovado", variant: "success" },
  APROVADO_COM_COMENTARIOS: { label: "Aprov. c/ Com.", variant: "warning" },
  REJEITADO: { label: "Rejeitado", variant: "error" },
};

const PROCESSAMENTO_CONFIG: Record<string, { label: string; variant: Variant }> = {
  pendente: { label: "Pendente", variant: "secondary" },
  processando: { label: "Processando", variant: "info" },
  concluido: { label: "Concluído", variant: "success" },
  erro: { label: "Erro", variant: "error" },
};

function BaseBadge({
  config,
  value,
}: {
  config: Record<string, { label: string; variant: Variant }>;
  value: string | null;
}) {
  if (!value) return null;
  const c = config[value];
  if (!c) return <Badge variant="outline">{value}</Badge>;
  return <Badge variant={c.variant}>{c.label}</Badge>;
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
