"use client";

import { UserButton, useUser } from "@clerk/nextjs";
import { Menu, UserCog } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/ui/logo";
import { useProfile } from "@/components/profile/profile-provider";
import { readProfile } from "@/components/profile/profile-dialog";

interface HeaderProps {
  onMenuClick?: () => void;
}

export function Header({ onMenuClick }: HeaderProps) {
  const { user } = useUser();
  const { openProfile } = useProfile();
  const apelido = readProfile(user?.unsafeMetadata).apelido;

  return (
    <header className="sticky top-0 z-(--z-sticky) flex h-14 items-center justify-between border-b border-edge bg-canvas/90 px-4 backdrop-blur supports-[backdrop-filter]:bg-canvas/75">
      <div className="flex items-center gap-3">
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

      <div className="flex items-center gap-3">
        {apelido && (
          <button
            type="button"
            onClick={openProfile}
            className="hidden text-[13px] text-fg-muted transition-colors hover:text-fg sm:block"
            title="Meu perfil"
          >
            {apelido}
          </button>
        )}
        <UserButton
          afterSignOutUrl="/"
          appearance={{
            elements: {
              avatarBox: "h-7 w-7 rounded-md",
            },
          }}
        >
          <UserButton.MenuItems>
            <UserButton.Action
              label="Meu perfil"
              labelIcon={<UserCog className="h-4 w-4" />}
              onClick={openProfile}
            />
          </UserButton.MenuItems>
        </UserButton>
      </div>
    </header>
  );
}
