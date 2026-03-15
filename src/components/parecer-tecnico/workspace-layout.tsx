"use client";

import { useState } from "react";
import { useWorkspace } from "./workspace-context";
import { WorkspaceTopbar } from "./workspace-topbar";
import { ItemListPanel } from "./item-list-panel";
import { ItemDetailPanel } from "./item-detail-panel";
import { OverviewPanel } from "./overview-panel";
import { AnalysisSetup } from "./analysis-setup";
import { ChatPanelWrapper } from "./chat-panel-wrapper";

type MobileTab = "lista" | "detalhe" | "chat";

export function WorkspaceLayout() {
  const { hasResults, selectedItemId, analyzing, parecer } = useWorkspace();
  const [mobileTab, setMobileTab] = useState<MobileTab>("lista");

  const showAnalysisSetup =
    !hasResults && !analyzing && parecer?.status_processamento !== "processando";
  const showAnalysisProgress =
    analyzing || parecer?.status_processamento === "processando";

  const renderCenterPanel = () => {
    if (showAnalysisSetup || showAnalysisProgress) {
      return <AnalysisSetup />;
    }
    if (selectedItemId) {
      return <ItemDetailPanel />;
    }
    return <OverviewPanel />;
  };

  return (
    <div className="flex h-full flex-col bg-bg-primary">
      <WorkspaceTopbar />

      {/* Mobile tab bar */}
      <div className="flex border-b border-border bg-surface lg:hidden">
        {(
          [
            { key: "lista", label: "Itens" },
            { key: "detalhe", label: "Detalhe" },
            { key: "chat", label: "Chat IA" },
          ] as const
        ).map((tab) => (
          <button
            key={tab.key}
            onClick={() => setMobileTab(tab.key)}
            className={`flex-1 px-4 py-2.5 text-sm font-medium transition-colors ${
              mobileTab === tab.key
                ? "border-b-2 border-accent text-accent"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Desktop: 3-panel grid */}
      <div className="hidden flex-1 overflow-hidden lg:grid lg:grid-cols-[320px_1fr_384px]">
        {/* Left panel - Item list */}
        <div className="overflow-y-auto border-r border-border bg-surface">
          {hasResults ? (
            <ItemListPanel />
          ) : (
            <div className="flex h-full items-center justify-center p-6 text-center text-sm text-text-tertiary">
              Os itens aparecerao aqui apos a analise.
            </div>
          )}
        </div>

        {/* Center panel */}
        <div className="overflow-y-auto">{renderCenterPanel()}</div>

        {/* Right panel - Chat */}
        <div className="flex flex-col overflow-hidden border-l border-border bg-surface">
          {hasResults ? (
            <ChatPanelWrapper />
          ) : (
            <div className="flex h-full items-center justify-center p-6 text-center text-sm text-text-tertiary">
              O chat com IA estara disponivel apos a analise.
            </div>
          )}
        </div>
      </div>

      {/* Mobile: tabbed view */}
      <div className="flex-1 overflow-y-auto lg:hidden">
        {mobileTab === "lista" && (
          <div className="bg-surface">
            {hasResults ? (
              <ItemListPanel onItemSelect={() => setMobileTab("detalhe")} />
            ) : (
              <div className="p-6 text-center text-sm text-text-tertiary">
                Os itens aparecerao aqui apos a analise.
              </div>
            )}
          </div>
        )}
        {mobileTab === "detalhe" && (
          <div>{renderCenterPanel()}</div>
        )}
        {mobileTab === "chat" && (
          <div className="flex h-full flex-col bg-surface">
            {hasResults ? (
              <ChatPanelWrapper />
            ) : (
              <div className="flex h-full items-center justify-center p-6 text-center text-sm text-text-tertiary">
                O chat com IA estara disponivel apos a analise.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
