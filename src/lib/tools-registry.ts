import {
  Languages,
  Table,
  FileText,
  Brain,
  BookOpen,
  BarChart3,
  Gauge,
  type LucideIcon,
} from "lucide-react";

// ── Category definitions ──────────────────────────────────────────────

export type CategoryId = "documentacao" | "conhecimento" | "analise" | "instrumentacao";

export interface Category {
  id: CategoryId;
  label: string;
  icon: LucideIcon;
  color: string;
}

export const categories: Category[] = [
  { id: "documentacao", label: "Documentação", icon: FileText, color: "bg-info-muted text-info" },
  { id: "conhecimento", label: "Conhecimento", icon: BookOpen, color: "bg-accent-muted text-accent" },
  { id: "analise", label: "Análise", icon: BarChart3, color: "bg-success-muted text-success" },
  { id: "instrumentacao", label: "Instrumentação", icon: Gauge, color: "bg-warning-muted text-warning" },
];

// ── Tool definitions ──────────────────────────────────────────────────

export interface Tool {
  id: string;
  title: string;
  description: string;
  icon: LucideIcon;
  href: string;
  category: CategoryId;
}

export const tools: Tool[] = [
  {
    id: "translate",
    title: "Tradutor AI",
    description: "Traduza textos técnicos com precisão usando IA",
    icon: Languages,
    href: "/dashboard/translate",
    category: "documentacao",
  },
  {
    id: "pdf-extractor",
    title: "Extrator de Tabelas",
    description: "Extraia tabelas de PDFs e exporte para Excel",
    icon: Table,
    href: "/dashboard/pdf-extractor",
    category: "documentacao",
  },
  {
    id: "pdf-converter",
    title: "PDF para Word",
    description: "Converta PDFs para documentos Word editáveis",
    icon: FileText,
    href: "/dashboard/pdf-converter",
    category: "documentacao",
  },
  {
    id: "rag",
    title: "Conhecimento (RAG)",
    description: "Consulte documentos técnicos com IA generativa",
    icon: Brain,
    href: "/dashboard/rag",
    category: "conhecimento",
  },
];

// ── Helpers ───────────────────────────────────────────────────────────

export function getToolsByCategory(): { category: Category; tools: Tool[] }[] {
  return categories
    .map((cat) => ({
      category: cat,
      tools: tools.filter((t) => t.category === cat.id),
    }))
    .filter((group) => group.tools.length > 0);
}
