import { getToolsByCategory, tools } from "@/lib/tools-registry";
import { ToolCard } from "@/components/dashboard/tool-card";
import { cn } from "@/lib/utils";

export default function DashboardPage() {
  const grouped = getToolsByCategory();

  return (
    <div className="space-y-10">
      {/* ── Header ── */}
      <div>
        <div className="flex items-baseline justify-between">
          <h1 className="text-2xl font-heading font-bold tracking-tight">
            Agentes
          </h1>
          <span className="text-sm text-text-secondary font-mono tabular-nums">
            {tools.length} agentes
          </span>
        </div>
        <p className="mt-1 text-sm text-text-tertiary">
          Agentes de engenharia com inteligência artificial
        </p>
      </div>

      {/* ── Category sections ── */}
      {grouped.map(({ category, tools: categoryTools }, groupIndex) => (
        <section key={category.id} className="space-y-4">
          {/* Separator between categories */}
          {groupIndex > 0 && (
            <div className="border-t border-border" />
          )}

          {/* Category header */}
          <div className="flex items-center gap-2.5 pt-1">
            <div
              className={cn(
                "flex h-7 w-7 items-center justify-center rounded",
                category.color
              )}
            >
              <category.icon className="h-4 w-4" />
            </div>
            <h2 className="text-sm font-heading font-semibold text-text-secondary uppercase tracking-wider">
              {category.label}
            </h2>
            <span className="text-xs text-text-tertiary font-mono tabular-nums">
              ({categoryTools.length})
            </span>
          </div>

          {/* Tools grid */}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {categoryTools.map((tool, toolIndex) => (
              <ToolCard
                key={tool.id}
                tool={tool}
                category={category}
                animationDelay={toolIndex * 75}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

