"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useUser } from "@clerk/nextjs";
import { Files, FilePlus, Gauge } from "lucide-react";
import { cn } from "@/lib/utils";
import { ScrollArea } from "@/components/ui/scroll-area";
import { isAdminEmail } from "@/lib/admin";
import { version } from "../../../package.json";

const PATEC = "/dashboard/parecer-tecnico";

interface SidebarProps {
  className?: string;
  /** fecha o sheet mobile ao navegar */
  onNavigate?: () => void;
}

export function Sidebar({ className, onNavigate }: SidebarProps) {
  const pathname = usePathname();
  const { user, isLoaded } = useUser();
  const isAdmin =
    isLoaded && isAdminEmail(user?.primaryEmailAddress?.emailAddress);

  const itemBase =
    "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px] leading-tight transition-colors";
  const itemActive =
    "bg-surface-2 text-fg shadow-[inset_2px_0_0_0_var(--accent-c)]";
  const itemIdle = "text-fg-muted hover:bg-surface-2/60 hover:text-fg";

  const isNovo = pathname === `${PATEC}/novo`;
  const isQualidade = pathname === `${PATEC}/qualidade`;
  // "Casos" cobre a lista e o caso aberto (/[id])
  const isCasos = !isNovo && !isQualidade && pathname.startsWith(PATEC);

  return (
    <aside
      className={cn(
        "flex h-full w-60 flex-col border-r border-edge bg-surface-1",
        className
      )}
    >
      <ScrollArea className="flex-1 px-3 py-4">
        <nav className="flex flex-col gap-0.5">
          <div className="mb-1 px-2.5">
            <span className="microlabel text-[10px]">Parecer Técnico</span>
          </div>

          <Link
            href={PATEC}
            onClick={onNavigate}
            className={cn(itemBase, isCasos ? itemActive : itemIdle)}
          >
            <Files className="h-4 w-4" />
            <span className="flex-1 font-medium">Casos</span>
          </Link>

          <Link
            href={`${PATEC}/novo`}
            onClick={onNavigate}
            className={cn(itemBase, isNovo ? itemActive : itemIdle)}
          >
            <FilePlus className="h-4 w-4" />
            <span className="flex-1 font-medium">Novo parecer</span>
          </Link>

          {isAdmin && (
            <Link
              href={`${PATEC}/qualidade`}
              onClick={onNavigate}
              className={cn(itemBase, isQualidade ? itemActive : itemIdle)}
            >
              <Gauge className="h-4 w-4" />
              <span className="flex-1 font-medium">Qualidade</span>
            </Link>
          )}
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
