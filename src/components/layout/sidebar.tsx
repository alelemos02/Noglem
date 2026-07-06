"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutGrid } from "lucide-react";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import { getToolsByCategory } from "@/lib/tools-registry";
import { version } from "../../../package.json";

interface SidebarProps {
  className?: string;
  /** fecha o sheet mobile ao navegar */
  onNavigate?: () => void;
}

export function Sidebar({ className, onNavigate }: SidebarProps) {
  const pathname = usePathname();
  const groups = getToolsByCategory();

  const itemBase =
    "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px] leading-tight transition-colors";
  const itemActive =
    "bg-surface-2 text-fg shadow-[inset_2px_0_0_0_var(--accent-c)]";
  const itemIdle = "text-fg-muted hover:bg-surface-2/60 hover:text-fg";

  return (
    <aside
      className={cn(
        "flex h-full w-60 flex-col border-r border-edge bg-surface-1",
        className
      )}
    >
      <ScrollArea className="flex-1 px-3 py-4">
        <nav className="flex flex-col gap-0.5">
          {/* Home */}
          <Link
            href="/dashboard"
            onClick={onNavigate}
            className={cn(
              itemBase,
              pathname === "/dashboard" ? itemActive : itemIdle
            )}
          >
            <LayoutGrid className="h-4 w-4" />
            <span className="flex-1 font-medium">Agentes</span>
          </Link>

          {/* Grupos por disciplina */}
          {groups.map(({ category, tools }) => (
            <div key={category.id} className="mt-4">
              <div className="mb-1 flex items-baseline justify-between px-2.5">
                <span className="microlabel text-[10px]">{category.label}</span>
                <span className="font-mono text-[10px] tabular-nums text-fg-disabled">
                  {String(tools.length).padStart(2, "0")}
                </span>
              </div>
              <div className="flex flex-col gap-0.5">
                {tools.map((tool) => {
                  const isActive = pathname.startsWith(tool.href);
                  if (tool.status === "coming_soon") {
                    return (
                      <div
                        key={tool.id}
                        className={cn(itemBase, "cursor-default text-fg-disabled")}
                      >
                        <span className="flex-1 truncate">{tool.title}</span>
                        <span className="rounded-xs border border-edge px-1 py-px font-mono text-[9px] uppercase tracking-[0.08em] text-fg-disabled">
                          breve
                        </span>
                      </div>
                    );
                  }
                  return (
                    <Link
                      key={tool.id}
                      href={tool.href}
                      onClick={onNavigate}
                      className={cn(itemBase, isActive ? itemActive : itemIdle)}
                    >
                      <span className="flex-1 truncate">{tool.title}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
      </ScrollArea>

      <div className="flex items-center justify-between border-t border-edge px-4 py-3.5">
        <p className="font-mono text-[11px] tabular-nums text-fg-subtle">
          v{version}
        </p>
        <p className="microlabel text-[9px]">noglem</p>
      </div>
    </aside>
  );
}
