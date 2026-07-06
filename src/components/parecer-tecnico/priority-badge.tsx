"use client";

import { Badge, type BadgeProps } from "@/components/ui/badge";

const PRIORITY_CONFIG: Record<string, NonNullable<BadgeProps["variant"]>> = {
  ALTA: "error",
  MEDIA: "warning",
  BAIXA: "success",
};

export function PriorityBadge({ priority }: { priority: string | null }) {
  if (!priority) return null;
  return (
    <Badge variant={PRIORITY_CONFIG[priority] ?? "secondary"}>{priority}</Badge>
  );
}
