import Link from "next/link";
import { getToolsByCategory, getStatusBadgeProps, tools } from "@/lib/tools-registry";
import type { Tool, Category } from "@/lib/tools-registry";
import {
  Card,
  CardContent,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export default function DashboardPage() {
  const grouped = getToolsByCategory();

  return (
    <div className="space-y-10">
      {/* ── Header ── */}
      <div>
        <div className="flex items-baseline justify-between">
          <h1 className="text-2xl font-heading font-bold tracking-tight">
            Ferramentas
          </h1>
          <span className="text-sm text-text-secondary font-mono tabular-nums">
            {tools.length} ferramentas
          </span>
        </div>
        <p className="mt-1 text-sm text-text-tertiary">
          Ferramentas de engenharia com inteligência artificial
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

/* ── Tool Card ── */

function ToolCard({
  tool,
  category,
  animationDelay,
}: {
  tool: Tool;
  category: Category;
  animationDelay: number;
}) {
  const isComingSoon = tool.status === "coming_soon";
  const badgeProps = getStatusBadgeProps(tool.status);

  const cardContent = (
    <Card
      interactive={!isComingSoon}
      className={cn(
        "h-full border-l-2 animate-fade-in-up",
        category.borderColor,
        isComingSoon && "opacity-50 cursor-default"
      )}
      style={{ animationDelay: `${animationDelay}ms`, animationFillMode: "backwards" }}
    >
      <CardContent className="flex items-start gap-3.5 p-4">
        {/* Icon */}
        <div
          className={cn(
            "mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
            category.color
          )}
        >
          <tool.icon className="h-5 w-5" />
        </div>

        {/* Text */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-heading font-semibold text-sm leading-tight">
              {tool.title}
            </h3>
            <Badge
              variant={badgeProps.variant}
              dot={badgeProps.dot}
              className="text-[10px] px-1.5 py-0"
            >
              {badgeProps.label}
            </Badge>
          </div>
          <p className="mt-1.5 text-xs text-text-secondary leading-relaxed">
            {tool.description}
          </p>
        </div>
      </CardContent>
    </Card>
  );

  if (isComingSoon) {
    return cardContent;
  }

  return (
    <Link href={tool.href}>
      {cardContent}
    </Link>
  );
}
