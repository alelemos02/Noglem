import Link from "next/link";
import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/ui/logo";
import { Languages, Table, FileText, ArrowRight } from "lucide-react";

const features = [
  {
    title: "Tradutor AI",
    description: "Traduza textos técnicos com precisão usando inteligência artificial",
    icon: Languages,
    color: "bg-info-muted text-info",
  },
  {
    title: "Extrator de Tabelas",
    description: "Extraia tabelas de PDFs e exporte para Excel automaticamente",
    icon: Table,
    color: "bg-success-muted text-success",
  },
  {
    title: "PDF para Word",
    description: "Converta seus PDFs para documentos Word editáveis",
    icon: FileText,
    color: "bg-warning-muted text-warning",
  },
];

export default async function HomePage() {
  const { userId } = await auth();

  if (userId) {
    redirect("/dashboard");
  }

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Header */}
      <header className="border-b border-border">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <Logo variant="full" size="sm" />
          <div className="flex items-center gap-4">
            <Link href="/sign-in">
              <Button variant="ghost">Entrar</Button>
            </Link>
            <Link href="/sign-up">
              <Button>Criar conta</Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="flex flex-1 flex-col items-center justify-center px-4 py-20 text-center">
        <h1 className="max-w-3xl text-4xl font-bold tracking-tight sm:text-5xl md:text-6xl">
          Ferramentas de Engenharia em um só lugar
        </h1>
        <p className="mt-6 max-w-2xl text-lg text-muted-foreground">
          Jul/IA é sua plataforma centralizada para ferramentas de engenharia.
          Traduza documentos e extraia dados de PDFs com IA.
        </p>
        <div className="mt-10 flex gap-4">
          <Link href="/sign-up">
            <Button size="lg" className="gap-2">
              Começar agora
              <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
          <Link href="/sign-in">
            <Button size="lg" variant="outline">
              Já tenho conta
            </Button>
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="border-t border-border bg-muted/30 py-20">
        <div className="container mx-auto px-4">
          <h2 className="mb-12 text-center text-3xl font-bold">
            Nossas Ferramentas
          </h2>
          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature) => (
              <div
                key={feature.title}
                className="rounded-lg border border-border bg-card p-6 transition-colors hover:border-accent/50"
              >
                <div className={`mb-4 flex h-12 w-12 items-center justify-center rounded-lg ${feature.color}`}>
                  <feature.icon className="h-6 w-6" />
                </div>
                <h3 className="mb-2 text-lg font-semibold">{feature.title}</h3>
                <p className="text-sm text-muted-foreground">
                  {feature.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-8">
        <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
          <p>&copy; {new Date().getFullYear()} Jul/IA. Todos os direitos reservados.</p>
        </div>
      </footer>
    </div>
  );
}
