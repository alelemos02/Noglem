"use client";

import Link from "next/link";
import type { Tool } from "@/lib/tools-registry";
import { getStatusBadgeProps } from "@/lib/tools-registry";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useAnalytics } from "@/hooks/use-analytics";

export function ToolCard({
  tool,
  animationDelay,
}: {
  tool: Tool;
  animationDelay: number;
}) {
  const { trackToolClicked } = useAnalytics();
  const isComingSoon = tool.status === "coming_soon";
  const badgeProps = getStatusBadgeProps(tool.status);

  const cardContent = (
    <Card
      interactive={!isComingSoon}
      className={cn(
        "h-full gap-0 py-0 animate-fade-in-up",
        isComingSoon && "opacity-50 cursor-default"
      )}
      style={{ animationDelay: `${animationDelay}ms`, animationFillMode: "backwards" }}
    >
      <CardContent className="flex h-full flex-col gap-2 p-4">
        <div className="flex items-center gap-2.5">
          <tool.icon className="h-[18px] w-[18px] shrink-0 text-fg-subtle" aria-hidden="true" />
          <h3 className="min-w-0 flex-1 truncate text-sm font-semibold leading-tight text-fg">
            {tool.title}
          </h3>
          <Badge
            variant={badgeProps.variant}
            dot={badgeProps.dot}
            className="px-1.5 py-0 text-[9px]"
          >
            {badgeProps.label}
          </Badge>
        </div>
        <p className="text-[13px] leading-relaxed text-fg-muted">
          {tool.description}
        </p>
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
