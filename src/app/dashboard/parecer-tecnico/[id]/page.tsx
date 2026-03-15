"use client";

import { use } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  ParecerWorkspaceProvider,
  useWorkspace,
} from "@/components/parecer-tecnico/workspace-context";
import { WorkspaceLayout } from "@/components/parecer-tecnico/workspace-layout";
import { useKeyboardShortcuts } from "@/components/parecer-tecnico/use-keyboard-shortcuts";

export default function ParecerDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);

  return (
    <ParecerWorkspaceProvider parecerId={id}>
      <ParecerWorkspaceContent />
    </ParecerWorkspaceProvider>
  );
}

function ParecerWorkspaceContent() {
  const { loading, notFound } = useWorkspace();
  useKeyboardShortcuts();

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <p className="text-text-tertiary">Carregando...</p>
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="flex h-96 flex-col items-center justify-center gap-4">
        <p className="text-lg text-text-secondary">Parecer não encontrado</p>
        <p className="text-sm text-text-tertiary">
          Este parecer pode ter sido excluído ou o link está incorreto.
        </p>
        <Link href="/dashboard/parecer-tecnico">
          <Button variant="outline">Voltar para a listagem</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="-m-6 h-[calc(100vh-3.5rem)]">
      <WorkspaceLayout />
    </div>
  );
}
