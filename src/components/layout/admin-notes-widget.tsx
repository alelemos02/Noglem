"use client";

import { useState, useEffect, useCallback } from "react";
import { useUser } from "@clerk/nextjs";
import { usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  StickyNote,
  X,
  Plus,
  Check,
  Trash2,
  Bug,
  Lightbulb,
  TrendingUp,
  ListTodo,
  Loader2,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

const ADMIN_EMAILS = [
  "alelemos02@gmail.com",
  "alexandre.nogueira@noglem.com.br",
  "admin@noglem.com.br",
];

interface AdminNote {
  id: string;
  title: string;
  content: string | null;
  category: string;
  tool_context: string | null;
  is_resolved: string;
  created_at: string;
  updated_at: string;
}

const CATEGORIES = [
  { value: "bug", label: "Bug", icon: Bug, color: "text-error" },
  { value: "idea", label: "Ideia", icon: Lightbulb, color: "text-warning" },
  { value: "improvement", label: "Melhoria", icon: TrendingUp, color: "text-info" },
  { value: "todo", label: "To-do", icon: ListTodo, color: "text-success" },
] as const;

function getCategoryInfo(category: string) {
  return CATEGORIES.find((c) => c.value === category) || CATEGORIES[1];
}

function getToolFromPath(pathname: string): string | null {
  const match = pathname.match(/\/dashboard\/([^/]+)/);
  return match ? match[1] : null;
}

export function AdminNotesWidget() {
  const { user, isLoaded } = useUser();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [notes, setNotes] = useState<AdminNote[]>([]);
  const [loading, setLoading] = useState(false);
  const [showResolved, setShowResolved] = useState(false);

  // Form state
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [category, setCategory] = useState("idea");
  const [saving, setSaving] = useState(false);

  const isAdmin =
    isLoaded &&
    ADMIN_EMAILS.includes(
      user?.primaryEmailAddress?.emailAddress || ""
    );

  const fetchNotes = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/admin-notes");
      if (res.ok) {
        setNotes(await res.json());
      }
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open && isAdmin) {
      fetchNotes();
    }
  }, [open, isAdmin, fetchNotes]);

  if (!isAdmin) return null;

  const pendingNotes = notes.filter((n) => n.is_resolved === "false");
  const resolvedNotes = notes.filter((n) => n.is_resolved === "true");

  const handleCreate = async () => {
    if (!title.trim()) return;
    setSaving(true);
    try {
      const res = await fetch("/api/admin-notes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title.trim(),
          content: content.trim() || null,
          category,
          tool_context: getToolFromPath(pathname),
        }),
      });
      if (res.ok) {
        setTitle("");
        setContent("");
        setCategory("idea");
        setShowForm(false);
        await fetchNotes();
      }
    } catch {
      // silent
    } finally {
      setSaving(false);
    }
  };

  const handleToggleResolved = async (note: AdminNote) => {
    const newValue = note.is_resolved === "true" ? "false" : "true";
    try {
      const res = await fetch(`/api/admin-notes/${note.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_resolved: newValue }),
      });
      if (res.ok) {
        setNotes((prev) =>
          prev.map((n) =>
            n.id === note.id ? { ...n, is_resolved: newValue } : n
          )
        );
      }
    } catch {
      // silent
    }
  };

  const handleDelete = async (noteId: string) => {
    try {
      const res = await fetch(`/api/admin-notes/${noteId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setNotes((prev) => prev.filter((n) => n.id !== noteId));
      }
    } catch {
      // silent
    }
  };

  const currentTool = getToolFromPath(pathname);

  return (
    <>
      {/* FAB */}
      <button
        onClick={() => setOpen(!open)}
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-lg bg-accent text-text-inverse shadow-lg transition-transform hover:scale-105 hover:bg-accent-hover active:scale-95"
        title="Notas do Admin"
      >
        {open ? <X className="h-6 w-6" /> : <StickyNote className="h-6 w-6" />}
        {!open && pendingNotes.length > 0 && (
          <span className="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-md bg-error text-[10px] font-mono font-bold text-white">
            {pendingNotes.length}
          </span>
        )}
      </button>

      {/* Panel */}
      {open && (
        <div className="fixed bottom-24 right-6 z-50 flex w-96 max-h-[70vh] flex-col overflow-hidden rounded-lg border border-border bg-bg-primary shadow-2xl">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <div>
              <h3 className="font-heading font-semibold text-text-primary">
                Notas do Admin
              </h3>
              {currentTool && (
                <p className="text-xs text-text-tertiary">
                  Contexto: <span className="font-mono">{currentTool}</span>
                </p>
              )}
            </div>
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={() => setShowForm(!showForm)}
              title="Nova nota"
            >
              <Plus className="h-4 w-4" />
            </Button>
          </div>

          {/* New note form */}
          {showForm && (
            <div className="border-b border-border bg-bg-secondary p-3 space-y-2">
              <Input
                placeholder="Titulo da nota..."
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="h-8 text-sm"
              />
              <textarea
                placeholder="Descricao (opcional)..."
                value={content}
                onChange={(e) => setContent(e.target.value)}
                className="w-full min-h-[60px] rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-border-focus focus:ring-1 focus:ring-accent resize-none"
              />
              <div className="flex gap-1">
                {CATEGORIES.map((cat) => {
                  const Icon = cat.icon;
                  return (
                    <button
                      key={cat.value}
                      onClick={() => setCategory(cat.value)}
                      className={`flex items-center gap-1 rounded-md px-2 py-1 text-xs transition-colors ${
                        category === cat.value
                          ? "bg-surface-active text-text-primary"
                          : "text-text-tertiary hover:bg-surface-hover"
                      }`}
                      title={cat.label}
                    >
                      <Icon className={`h-3 w-3 ${cat.color}`} />
                      {cat.label}
                    </button>
                  );
                })}
              </div>
              <div className="flex justify-end gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowForm(false)}
                >
                  Cancelar
                </Button>
                <Button
                  size="sm"
                  onClick={handleCreate}
                  loading={saving}
                  disabled={!title.trim()}
                >
                  Salvar
                </Button>
              </div>
            </div>
          )}

          {/* Notes list */}
          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-5 w-5 animate-spin text-text-tertiary" />
              </div>
            ) : pendingNotes.length === 0 && !showForm ? (
              <div className="py-8 text-center text-sm text-text-tertiary">
                Nenhuma nota pendente.
              </div>
            ) : (
              <div className="divide-y divide-border">
                {pendingNotes.map((note) => {
                  const catInfo = getCategoryInfo(note.category);
                  const CatIcon = catInfo.icon;
                  return (
                    <div
                      key={note.id}
                      className="group flex items-start gap-3 px-4 py-3 hover:bg-surface-hover transition-colors"
                    >
                      <CatIcon
                        className={`mt-0.5 h-4 w-4 shrink-0 ${catInfo.color}`}
                      />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-text-primary truncate">
                          {note.title}
                        </p>
                        {note.content && (
                          <p className="mt-0.5 text-xs text-text-secondary line-clamp-2">
                            {note.content}
                          </p>
                        )}
                        <div className="mt-1 flex items-center gap-2">
                          <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                            {catInfo.label}
                          </Badge>
                          {note.tool_context && (
                            <span className="text-[10px] font-mono text-text-tertiary">
                              {note.tool_context}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex shrink-0 gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => handleToggleResolved(note)}
                          className="rounded-md p-1 text-text-tertiary hover:bg-success-muted hover:text-success transition-colors"
                          title="Marcar como resolvida"
                        >
                          <Check className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => handleDelete(note.id)}
                          className="rounded-md p-1 text-text-tertiary hover:bg-error-muted hover:text-error transition-colors"
                          title="Excluir nota"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Resolved section */}
            {resolvedNotes.length > 0 && (
              <div className="border-t border-border">
                <button
                  onClick={() => setShowResolved(!showResolved)}
                  className="flex w-full items-center justify-between px-4 py-2 text-xs text-text-tertiary hover:bg-surface-hover transition-colors"
                >
                  <span>Resolvidas ({resolvedNotes.length})</span>
                  {showResolved ? (
                    <ChevronUp className="h-3 w-3" />
                  ) : (
                    <ChevronDown className="h-3 w-3" />
                  )}
                </button>
                {showResolved && (
                  <div className="divide-y divide-border">
                    {resolvedNotes.map((note) => {
                      const catInfo = getCategoryInfo(note.category);
                      const CatIcon = catInfo.icon;
                      return (
                        <div
                          key={note.id}
                          className="group flex items-start gap-3 px-4 py-2 opacity-60 hover:opacity-100 transition-opacity"
                        >
                          <CatIcon
                            className={`mt-0.5 h-4 w-4 shrink-0 ${catInfo.color}`}
                          />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm text-text-secondary line-through truncate">
                              {note.title}
                            </p>
                          </div>
                          <div className="flex shrink-0 gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button
                              onClick={() => handleToggleResolved(note)}
                              className="rounded-md p-1 text-text-tertiary hover:bg-warning-muted hover:text-warning transition-colors"
                              title="Reabrir"
                            >
                              <Check className="h-3.5 w-3.5" />
                            </button>
                            <button
                              onClick={() => handleDelete(note.id)}
                              className="rounded-md p-1 text-text-tertiary hover:bg-error-muted hover:text-error transition-colors"
                              title="Excluir"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
