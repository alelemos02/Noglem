"use client";

const PRIORITY_CONFIG: Record<string, string> = {
  ALTA: "bg-red-900/40 text-red-400 border-red-700/50",
  MEDIA: "bg-yellow-900/40 text-yellow-400 border-yellow-700/50",
  BAIXA: "bg-green-900/40 text-green-400 border-green-700/50",
};

export function PriorityBadge({ priority }: { priority: string | null }) {
  if (!priority) return null;
  const cls = PRIORITY_CONFIG[priority] || "bg-gray-800/60 text-gray-400 border-gray-600/50";
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${cls}`}>
      {priority}
    </span>
  );
}
