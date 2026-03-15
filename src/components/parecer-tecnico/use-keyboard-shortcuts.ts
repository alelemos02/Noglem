"use client";

import { useEffect } from "react";
import { useWorkspace } from "./workspace-context";

const STATUS_MAP: Record<string, string> = {
  "1": "A",
  "2": "B",
  "3": "C",
  "4": "D",
  "5": "E",
};

interface UseKeyboardShortcutsOptions {
  onToggleHelp?: () => void;
}

export function useKeyboardShortcuts({
  onToggleHelp,
}: UseKeyboardShortcutsOptions = {}) {
  const {
    selectedItemId,
    selectedItem,
    selectNextItem,
    selectPreviousItem,
    selectItem,
    updateItem,
  } = useWorkspace();

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if ((e.target as HTMLElement).isContentEditable) return;

      switch (e.key) {
        case "j":
        case "ArrowDown":
          e.preventDefault();
          selectNextItem();
          break;

        case "k":
        case "ArrowUp":
          e.preventDefault();
          selectPreviousItem();
          break;

        case "Escape":
          selectItem(null);
          break;

        case "?":
          onToggleHelp?.();
          break;

        case "1":
        case "2":
        case "3":
        case "4":
        case "5": {
          if (!selectedItemId || !selectedItem) return;
          const newStatus = STATUS_MAP[e.key];
          if (newStatus && newStatus !== selectedItem.status) {
            e.preventDefault();
            updateItem(selectedItemId, { status: newStatus });
          }
          break;
        }
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [
    selectedItemId,
    selectedItem,
    selectNextItem,
    selectPreviousItem,
    selectItem,
    updateItem,
    onToggleHelp,
  ]);
}
