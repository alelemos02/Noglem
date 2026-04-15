"use client";

export default function PrensaCaboPage() {
  return (
    <div className="flex flex-col h-[calc(100vh-4rem)]">
      <iframe
        src="/tools/prensa-cabo.html"
        className="flex-1 w-full border-0"
        title="Prensa Cabo Analyzer"
      />
    </div>
  );
}
