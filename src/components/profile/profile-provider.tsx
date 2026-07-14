"use client";

/**
 * ProfileProvider — gate de onboarding + acesso à edição do perfil.
 *
 * Ao logar (inclusive via Google), se o usuário ainda não tem apelido, abre o
 * ProfileDialog em modo obrigatório. `useProfile().openProfile()` reabre o
 * diálogo para edição (chamado pelo header, ao clicar no apelido/foto).
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useUser } from "@clerk/nextjs";
import { ProfileDialog, readProfile } from "./profile-dialog";

interface ProfileContextValue {
  openProfile: () => void;
}

const ProfileContext = createContext<ProfileContextValue | null>(null);

export function useProfile(): ProfileContextValue {
  const ctx = useContext(ProfileContext);
  if (!ctx) {
    throw new Error("useProfile deve ser usado dentro de <ProfileProvider>");
  }
  return ctx;
}

export function ProfileProvider({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn, user } = useUser();
  const [open, setOpen] = useState(false);
  const [forced, setForced] = useState(false);

  // Gate de onboarding: sem apelido → abre obrigatório.
  useEffect(() => {
    if (!isLoaded || !isSignedIn || !user) return;
    const p = readProfile(user.unsafeMetadata);
    if (!p.apelido) {
      setForced(true);
      setOpen(true);
    }
  }, [isLoaded, isSignedIn, user]);

  const openProfile = useCallback(() => {
    setForced(false);
    setOpen(true);
  }, []);

  return (
    <ProfileContext.Provider value={{ openProfile }}>
      {children}
      <ProfileDialog open={open} onOpenChange={setOpen} forced={forced} />
    </ProfileContext.Provider>
  );
}
