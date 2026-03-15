"use client";

interface KeyboardHelpProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const SHORTCUTS = [
  { key: "j / ↓", description: "Proximo item" },
  { key: "k / ↑", description: "Item anterior" },
  { key: "1", description: "Classificar como A (Aprovado)" },
  { key: "2", description: "Classificar como B (Aprov. c/ Com.)" },
  { key: "3", description: "Classificar como C (Rejeitado)" },
  { key: "4", description: "Classificar como D (Info Ausente)" },
  { key: "5", description: "Classificar como E (Adicional)" },
  { key: "Esc", description: "Deselecionar item" },
  { key: "?", description: "Mostrar/ocultar esta ajuda" },
];

export function KeyboardHelp({ open, onOpenChange }: KeyboardHelpProps) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={() => onOpenChange(false)}
    >
      <div
        className="w-full max-w-md rounded-lg border border-border bg-surface p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-4 text-lg font-bold text-text-primary">
          Atalhos de Teclado
        </h2>
        <div className="space-y-1">
          {SHORTCUTS.map((s) => (
            <div
              key={s.key}
              className="flex items-center justify-between rounded px-2 py-1.5 hover:bg-surface-hover"
            >
              <span className="text-sm text-text-secondary">
                {s.description}
              </span>
              <kbd className="rounded border border-border bg-white/10 px-2 py-0.5 font-mono text-xs text-text-primary">
                {s.key}
              </kbd>
            </div>
          ))}
        </div>
        <div className="mt-4 text-right">
          <button
            onClick={() => onOpenChange(false)}
            className="rounded-md px-3 py-1.5 text-sm text-text-secondary hover:bg-surface-hover hover:text-text-primary"
          >
            Fechar
          </button>
        </div>
      </div>
    </div>
  );
}
