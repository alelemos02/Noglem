"use client";

import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/ui/logo";

interface HeaderProps {
  onMenuClick?: () => void;
}

// UserButton is lazy-imported so it only loads when Clerk is active
let ClerkUserButton: React.ComponentType<{ afterSignOutUrl?: string; appearance?: object }> | null = null;
if (typeof window !== "undefined" || process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY) {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    ClerkUserButton = require("@clerk/nextjs").UserButton;
  } catch {
    ClerkUserButton = null;
  }
}

const LOCAL_DEV = process.env.NEXT_PUBLIC_LOCAL_DEV === "true";

export function Header({ onMenuClick }: HeaderProps) {
  return (
    <header className="sticky top-0 z-50 flex h-16 items-center justify-between border-b border-border bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden"
          onClick={onMenuClick}
        >
          <Menu className="h-5 w-5" />
          <span className="sr-only">Menu</span>
        </Button>

        <Logo variant="full" size="sm" />
      </div>

      <div className="flex items-center gap-4">
        {LOCAL_DEV ? (
          <span className="rounded-full bg-warning-muted px-3 py-1 text-xs font-medium text-warning">
            Dev Local
          </span>
        ) : ClerkUserButton ? (
          <ClerkUserButton
            afterSignOutUrl="/"
            appearance={{ elements: { avatarBox: "h-8 w-8" } }}
          />
        ) : null}
      </div>
    </header>
  );
}
