import Link from "next/link";
import { getToolsByCategory, tools } from "@/lib/tools-registry";
import {
  Card,
  CardContent,
} from "@/components/ui/card";

export default function DashboardPage() {
  const grouped = getToolsByCategory();

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-baseline justify-between">
        <h1 className="text-2xl font-heading font-bold tracking-tight">
          Ferramentas
        </h1>
        <span className="text-sm text-text-secondary font-mono tabular-nums">
          {tools.length} ferramentas
        </span>
      </div>

      {/* Category sections */}
      {grouped.map(({ category, tools: categoryTools }) => (
        <section key={category.id} className="space-y-3">
          {/* Category header */}
          <div className="flex items-center gap-2">
            <div
              className={`flex h-6 w-6 items-center justify-center rounded ${category.color}`}
            >
              <category.icon className="h-3.5 w-3.5" />
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
            {categoryTools.map((tool) => (
              <Link key={tool.id} href={tool.href}>
                <Card interactive className="h-full">
                  <CardContent className="flex items-start gap-3 p-4">
                    <div
                      className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded ${category.color}`}
                    >
                      <tool.icon className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <h3 className="font-heading font-semibold text-sm leading-tight">
                        {tool.title}
                      </h3>
                      <p className="mt-1 text-xs text-text-secondary leading-relaxed">
                        {tool.description}
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
