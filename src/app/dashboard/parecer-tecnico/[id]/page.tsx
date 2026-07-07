"use client";

import { use } from "react";
import { ConversationProvider } from "@/components/parecer-tecnico/conversation-provider";
import { ConversationScreen } from "@/components/parecer-tecnico/conversation-screen";

export default function ParecerDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);

  return (
    <div className="-m-6 h-[calc(100vh-3.5rem)]">
      <ConversationProvider parecerId={id}>
        <ConversationScreen />
      </ConversationProvider>
    </div>
  );
}
