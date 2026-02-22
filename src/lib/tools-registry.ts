import {
  Languages,
  Table,
  FileText,
  Brain,
  BookOpen,
  BarChart3,
  Gauge,
  FileCheck,
  MessageSquare,
  Users,
  ShieldCheck,
  GitCompare,
  FileSpreadsheet,
  type LucideIcon,
} from "lucide-react";

// ── Category definitions ──────────────────────────────────────────────

export type CategoryId = "documentacao" | "conhecimento" | "analise" | "instrumentacao";

export interface Category {
  id: CategoryId;
  label: string;
  icon: LucideIcon;
  color: string;
  borderColor: string;
}

export const categories: Category[] = [
  { id: "documentacao", label: "Documentação", icon: FileText, color: "bg-info-muted text-info", borderColor: "border-info" },
  { id: "conhecimento", label: "Conhecimento", icon: BookOpen, color: "bg-accent-muted text-accent", borderColor: "border-accent" },
  { id: "analise", label: "Análise", icon: BarChart3, color: "bg-success-muted text-success", borderColor: "border-success" },
  { id: "instrumentacao", label: "Instrumentação", icon: Gauge, color: "bg-warning-muted text-warning", borderColor: "border-warning" },
];

// ── Tool definitions ──────────────────────────────────────────────────

export type ToolStatus = "live" | "beta" | "coming_soon";

export interface Tool {
  id: string;
  title: string;
  description: string;
  icon: LucideIcon;
  href: string;
  category: CategoryId;
  status: ToolStatus;
}

export const tools: Tool[] = [
  {
    id: "translate",
    title: "Tradutor AI",
    description: "Traduza textos técnicos com precisão usando IA",
    icon: Languages,
    href: "/dashboard/translate",
    category: "documentacao",
    status: "live",
  },
  {
    id: "pdf-extractor",
    title: "Extrator de Tabelas",
    description: "Extraia tabelas de PDFs e exporte para Excel",
    icon: Table,
    href: "/dashboard/pdf-extractor",
    category: "documentacao",
    status: "beta",
  },
  {
    id: "pdf-converter",
    title: "PDF para Word",
    description: "Converta PDFs para documentos Word editáveis",
    icon: FileText,
    href: "/dashboard/pdf-converter",
    category: "documentacao",
    status: "beta",
  },
  {
    id: "rag",
    title: "Conhecimento (RAG)",
    description: "Consulte documentos técnicos com IA generativa",
    icon: Brain,
    href: "/dashboard/rag",
    category: "conhecimento",
    status: "beta",
  },
  {
    id: "parecer-tecnico",
    title: "Parecer Técnico",
    description: "Análise e comparação de documentação da engenharia versus documentos dos fornecedores",
    icon: FileCheck,
    href: "/dashboard/parecer-tecnico",
    category: "analise",
    status: "coming_soon",
  },
  {
    id: "responder-comentarios",
    title: "Responder Comentários",
    description: "Analise os comentários do cliente, categorize e responda a cada um deles",
    icon: MessageSquare,
    href: "/dashboard/responder-comentarios",
    category: "documentacao",
    status: "coming_soon",
  },
  {
    id: "resumo-reuniao",
    title: "Resumo de Reunião",
    description: "Faça o resumo completo, crie a ata e organize os responsáveis a partir da transcrição",
    icon: Users,
    href: "/dashboard/resumo-reuniao",
    category: "documentacao",
    status: "coming_soon",
  },
  {
    id: "consistencia-projeto",
    title: "Consistência de Projeto",
    description: "Análise de consistência para levantar problemas conceituais e sugerir melhorias",
    icon: ShieldCheck,
    href: "/dashboard/consistencia-projeto",
    category: "analise",
    status: "coming_soon",
  },
  {
    id: "comparar-projetos",
    title: "Comparar Projetos",
    description: "A IA analisa o projeto comparado e sugere melhorias com base na referência",
    icon: GitCompare,
    href: "/dashboard/comparar-projetos",
    category: "analise",
    status: "coming_soon",
  },
  {
    id: "elaboracao-folha-dados",
    title: "Elaboração de Folha de Dados",
    description: "A partir de documentos de referência, elabore rapidamente a folha de dados",
    icon: FileSpreadsheet,
    href: "/dashboard/elaboracao-folha-dados",
    category: "instrumentacao",
    status: "coming_soon",
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

/** Maps ToolStatus to Badge variant and label for consistent display */
export function getStatusBadgeProps(status: ToolStatus): {
  variant: "success" | "info" | "secondary";
  label: string;
  dot: boolean;
} {
  switch (status) {
    case "live":
      return { variant: "success", label: "Live", dot: true };
    case "beta":
      return { variant: "info", label: "Beta", dot: false };
    case "coming_soon":
      return { variant: "secondary", label: "Em breve", dot: false };
  }
}
