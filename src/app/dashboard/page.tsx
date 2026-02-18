import Link from "next/link";
import { currentUser } from "@clerk/nextjs/server";
import {
  Languages,
  Table,
  FileText,
  ArrowRight,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const tools = [
  {
    id: "translate",
    title: "Tradutor AI",
    description: "Traduza textos técnicos com precisão usando Google Gemini",
    icon: Languages,
    href: "/dashboard/translate",
    status: "live" as const,
    color: "bg-info-muted text-info",
  },
  {
    id: "pdf-extractor",
    title: "Extrator de Tabelas",
    description: "Extraia tabelas de PDFs e exporte para Excel",
    icon: Table,
    href: "/dashboard/pdf-extractor",
    status: "beta" as const,
    color: "bg-success-muted text-success",
  },
  {
    id: "pdf-converter",
    title: "PDF para Word",
    description: "Converta PDFs para documentos Word editáveis",
    icon: FileText,
    href: "/dashboard/pdf-converter",
    status: "beta" as const,
    color: "bg-warning-muted text-warning",
  },
];

const statusConfig = {
  live: { label: "Live", variant: "success" as const },
  beta: { label: "Beta", variant: "secondary" as const },
};

export default async function DashboardPage() {
  const user = await currentUser();
  const firstName = user?.firstName || "Usuário";

  return (
    <div className="space-y-8">
      {/* Welcome Section */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          Olá, {firstName}!
        </h1>
        <p className="mt-2 text-muted-foreground">
          Escolha uma ferramenta para começar
        </p>
      </div>

      {/* Tools Grid */}
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-2">
        {tools.map((tool) => (
          <Card
            key={tool.id}
            className="group relative overflow-hidden transition-all hover:border-accent/50 hover:shadow-lg"
          >
            <CardHeader>
              <div className="flex items-start justify-between">
                <div
                  className={`flex h-12 w-12 items-center justify-center rounded-lg ${tool.color}`}
                >
                  <tool.icon className="h-6 w-6" />
                </div>
                <Badge variant={statusConfig[tool.status].variant} dot>
                  {statusConfig[tool.status].label}
                </Badge>
              </div>
              <CardTitle className="mt-4">{tool.title}</CardTitle>
              <CardDescription>{tool.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <Link href={tool.href}>
                <Button className="w-full gap-2">
                  Acessar
                  <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                </Button>
              </Link>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Quick Stats */}
      <div className="rounded-lg border border-border bg-card p-6">
        <h2 className="mb-4 text-lg font-semibold">Atividade Recente</h2>
        <p className="text-sm text-muted-foreground">
          Nenhuma atividade registrada ainda. Comece usando uma das ferramentas acima!
        </p>
      </div>
    </div>
  );
}
