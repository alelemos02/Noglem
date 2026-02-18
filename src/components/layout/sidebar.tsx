"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Languages,
  Table,
  FileText,
  Home,
  Brain,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";

const menuItems = [
  {
    title: "Dashboard",
    href: "/dashboard",
    icon: Home,
  },
  {
    title: "Tradutor AI",
    href: "/dashboard/translate",
    icon: Languages,
    badge: "Live",
  },
  {
    title: "Conhecimento (RAG)",
    href: "/dashboard/rag",
    icon: Brain,
    badge: "Beta",
  },
  {
    title: "Extrator de Tabelas",
    href: "/dashboard/pdf-extractor",
    icon: Table,
    badge: "Beta",
  },
  {
    title: "PDF para Word",
    href: "/dashboard/pdf-converter",
    icon: FileText,
    badge: "Beta",
  },
];

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
          {menuItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-sidebar-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground"
                )}
              >
                <item.icon className="h-4 w-4" />
                <span className="flex-1">{item.title}</span>
                {item.badge && (
                  <Badge
                    variant={
                      item.badge === "Live"
                        ? "success"
                        : item.badge === "Beta"
                          ? "secondary"
                          : "outline"
                    }
                    className="text-xs"
                  >
                    {item.badge}
                  </Badge>
                )}
              </Link>
            );
          })}
        </nav>
      </ScrollArea>

      <div className="border-t border-border p-4">
        <p className="text-xs text-muted-foreground">
          Julia v2.0.0
        </p>
      </div>
    </aside>
  );
}
