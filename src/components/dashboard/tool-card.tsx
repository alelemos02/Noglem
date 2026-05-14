"use client";

import Link from "next/link";
import type { Tool, Category } from "@/lib/tools-registry";
import { getStatusBadgeProps } from "@/lib/tools-registry";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useAnalytics } from "@/hooks/use-analytics";

export function ToolCard({
  tool,
  category,
  animationDelay,
}: {
  tool: Tool;
  category: Category;
  animationDelay: number;
}) {
  const { trackToolClicked } = useAnalytics();
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
        <div
          className={cn(
            "mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
            category.color
          )}
        >
          <tool.icon className="h-5 w-5" />
        </div>

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
    <Link
      href={tool.href}
      onClick={() =>
        trackToolClicked({
          tool_id: tool.id,
          tool_title: tool.title,
          tool_category: tool.category,
        })
      }
    >
      {cardContent}
    </Link>
  );
}
