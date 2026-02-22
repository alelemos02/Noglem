"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home } from "lucide-react";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { tools, getStatusBadgeProps } from "@/lib/tools-registry";

interface SidebarProps {
  className?: string;
}

export function Sidebar({ className }: SidebarProps) {
  const pathname = usePathname();

  return (
    <aside
      className={cn(
        "flex h-full w-64 flex-col border-r border-border bg-sidebar",
        className
      )}
    >
      <ScrollArea className="flex-1 px-3 py-4">
        <nav className="space-y-1">
          {/* Dashboard */}
          <Link
            href="/dashboard"
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors border-l-2",
              pathname === "/dashboard"
                ? "border-accent bg-surface-active text-text-primary"
                : "border-transparent text-sidebar-foreground hover:bg-surface-hover hover:text-text-primary"
            )}
          >
            <Home className="h-4 w-4" />
            <span className="flex-1">Dashboard</span>
          </Link>

          {/* Separator */}
          <div className="!my-3 border-t border-border" />

          {/* Tools */}
          {tools.map((tool) => {
            const isActive = pathname === tool.href;
            const isComingSoon = tool.status === "coming_soon";
            const badgeProps = getStatusBadgeProps(tool.status);

            if (isComingSoon) {
              return (
                <div
                  key={tool.id}
                  className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-text-disabled cursor-default border-l-2 border-transparent"
                >
                  <tool.icon className="h-4 w-4" />
                  <span className="flex-1 truncate">{tool.title}</span>
                  <Badge
                    variant={badgeProps.variant}
                    className="text-[10px] px-1.5 py-0"
                  >
                    {badgeProps.label}
                  </Badge>
                </div>
              );
            }

            return (
              <Link
                key={tool.id}
                href={tool.href}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors border-l-2",
                  isActive
                    ? "border-accent bg-surface-active text-text-primary"
                    : "border-transparent text-sidebar-foreground hover:bg-surface-hover hover:text-text-primary"
                )}
              >
                <tool.icon className="h-4 w-4" />
                <span className="flex-1 truncate">{tool.title}</span>
                <Badge
                  variant={badgeProps.variant}
                  dot={badgeProps.dot}
                  className="text-[10px] px-1.5 py-0"
                >
                  {badgeProps.label}
                </Badge>
              </Link>
            );
          })}
        </nav>
      </ScrollArea>

      <div className="border-t border-border p-4">
        <p className="text-xs text-muted-foreground font-mono tabular-nums">
          Jul/IA v2.0.0
        </p>
      </div>
    </aside>
  );
}
