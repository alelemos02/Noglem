"use client";

/**
 * Renderização das entradas da thread:
 * - JulIA: sem balão fechado — avatar "J" + texto sobre o fundo (como Claude Code)
 * - Usuário: balão discreto à direita
 * - Evento: card compacto de workflow congelado
 */

import Markdown from "react-markdown";
import { Spinner } from "@/components/ui/spinner";
import type { TimelineEntry } from "./types";

function horario(at: string): string {
  return new Date(at).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function JuliaAvatar() {
  return (
    <div className="flex h-7 w-7 shrink-0 select-none items-center justify-center rounded-full bg-accent font-sans text-sm font-bold text-accent-fg">
      J
    </div>
  );
}

export function JuliaSpeech({
  markdown,
  at,
  streaming,
}: {
  markdown: string;
  at?: string;
  streaming?: boolean;
}) {
  return (
    <div className="flex gap-3 animate-fade-in">
      <JuliaAvatar />
      <div className="min-w-0 flex-1 pt-0.5">
        <div className="prose prose-sm prose-invert max-w-none text-[15px] leading-relaxed text-fg prose-p:my-1.5 prose-ul:my-1.5 prose-ol:my-1.5 prose-li:my-0.5 prose-headings:my-2 prose-strong:text-fg">
          <Markdown>{markdown}</Markdown>
        </div>
        {streaming && (
          <span className="mt-1 inline-flex items-center gap-1.5 text-xs text-fg-subtle">
            <Spinner size="xs" /> digitando...
          </span>
        )}
        {at && !streaming && (
          <p className="mt-1 text-[11px] text-fg-disabled">{horario(at)}</p>
        )}
      </div>
    </div>
  );
}

export function UserSpeech({ text, at }: { text: string; at?: string }) {
  return (
    <div className="flex justify-end animate-fade-in">
      <div className="max-w-[80%]">
        <div className="rounded-xl rounded-br-xs bg-surface-3 px-4 py-2.5 text-sm text-fg">
          <p className="whitespace-pre-wrap">{text}</p>
        </div>
        {at && (
          <p className="mt-1 text-right text-[11px] text-fg-disabled">
            {horario(at)}
          </p>
        )}
      </div>
    </div>
  );
}

const TONE_STYLES: Record<string, string> = {
  neutral: "border-edge text-fg-muted",
  success: "border-success/30 text-success-text",
  warning: "border-warning/30 text-warning-text",
  error: "border-danger/30 text-danger-text",
};

const TONE_ICONS: Record<string, string> = {
  neutral: "•",
  success: "✓",
  warning: "△",
  error: "✕",
};

export function EventCard({
  title,
  detail,
  at,
  tone = "neutral",
}: {
  title: string;
  detail?: string;
  at?: string;
  tone?: "neutral" | "success" | "warning" | "error";
}) {
  return (
    <div className="flex justify-center animate-fade-in">
      <div
        className={`inline-flex max-w-full items-baseline gap-2 rounded-lg border bg-surface-1/50 px-3 py-1.5 text-xs ${TONE_STYLES[tone]}`}
      >
        <span aria-hidden>{TONE_ICONS[tone]}</span>
        <span className="font-medium">{title}</span>
        {detail && (
          <span className="min-w-0 truncate text-fg-subtle" title={detail}>
            {detail}
          </span>
        )}
        {at && (
          <span className="shrink-0 text-fg-disabled">{horario(at)}</span>
        )}
      </div>
    </div>
  );
}

export function TimelineEntryView({ entry }: { entry: TimelineEntry }) {
  if (entry.kind === "julia") {
    return <JuliaSpeech markdown={entry.markdown} at={entry.at} />;
  }
  if (entry.kind === "user") {
    return <UserSpeech text={entry.text} at={entry.at} />;
  }
  // entradas "widget" são renderizadas pela thread (EphemeralEntry)
  if (entry.kind === "widget") return null;
  return (
    <EventCard
      title={entry.title}
      detail={entry.detail}
      at={entry.at}
      tone={entry.tone}
    />
  );
}
