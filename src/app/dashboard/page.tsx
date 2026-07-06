"use client";

import { getToolsByCategory, visibleTools } from "@/lib/tools-registry";
import { ToolCard } from "@/components/dashboard/tool-card";

export default function DashboardPage() {
  const grouped = getToolsByCategory();

  return (
    <div className="space-y-9">
      {/* ── Header ── */}
      <div>
        <div className="flex items-baseline gap-3">
          <h1 className="text-xl font-semibold tracking-tight text-fg">
            Agentes
          </h1>
          <span className="font-mono text-xs tabular-nums text-fg-subtle">
            {visibleTools.length} ferramentas
          </span>
        </div>
        <p className="mt-1.5 text-[13px] text-fg-muted">
          Ferramentas de IA para documentação, análise e instrumentação.
        </p>
      </div>

      {/* ── Category sections ── */}
      {grouped.map(({ category, tools: categoryTools }, groupIndex) => (
        <section key={category.id} className="space-y-3">
          {groupIndex > 0 && <div className="border-t border-edge" />}

          <div className="flex items-baseline gap-2.5 pt-1">
            <h2 className="microlabel">{category.label}</h2>
            <span className="font-mono text-[10px] tabular-nums text-fg-disabled">
              {String(categoryTools.length).padStart(2, "0")}
            </span>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {categoryTools.map((tool, toolIndex) => (
              <ToolCard
                key={tool.id}
                tool={tool}
                animationDelay={toolIndex * 75}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
