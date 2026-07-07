"use client";

/**
 * WidgetFrame — moldura padrão dos widgets interativos embutidos na conversa.
 */

import type { ReactNode } from "react";

export function WidgetFrame({
  children,
  title,
}: {
  children: ReactNode;
  title?: string;
}) {
  return (
    <div className="animate-fade-in-up rounded-xl border border-edge bg-surface-1 p-4">
      {title && (
        <p className="mb-3 font-sans text-xs font-semibold uppercase tracking-wider text-fg-subtle">
          {title}
        </p>
      )}
      {children}
    </div>
  );
}
