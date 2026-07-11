import Link from "next/link"
import { auth } from "@clerk/nextjs/server"
import { redirect } from "next/navigation"
import {
  ArrowRight,
  Languages,
  Library,
  MessageSquareText,
  ShieldCheck,
  Table2,
} from "lucide-react"
import { MarketingNav } from "@/components/marketing/nav"
import { MarketingFooter } from "@/components/marketing/footer"
import { ParecerMock } from "@/components/marketing/parecer-mock"
import { Section, SectionHeading } from "@/components/marketing/section"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { site } from "@/lib/site"

const trustItems = [
  "Workspaces isolados por projeto",
  "NDA em contrato",
  "Seus documentos não treinam modelos de IA",
]

const painPoints = [
  {
    title: "Horas de engenharia sênior em trabalho repetitivo",
    description:
      "Comparar propostas requisito a requisito consome as horas mais caras do projeto em conferência manual.",
  },
  {
    title: "Desvios descobertos tarde custam caro",
    description:
      "Uma omissão que passa na equalização reaparece na obra como pleito, aditivo ou atraso de comissionamento.",
  },
  {
    title: "Planilhas sem rastreabilidade",
    description:
      "Meses depois, ninguém consegue dizer por que um desvio foi aceito nem onde o fornecedor confirmou determinado ponto.",
  },
]

const steps = [
  {
    number: "01",
    title: "Requisitos",
    description:
      "Carregue a requisição, as folhas de dados e as especificações do projeto. A JulIA estrutura os requisitos que servem de base para toda a análise.",
  },
  {
    number: "02",
    title: "Análise das propostas",
    description:
      "Cada proposta é confrontada requisito a requisito. Desvios, omissões e itens excedentes são classificados e apontados com referência ao documento e à página de origem.",
  },
  {
    number: "03",
    title: "Ciclo com o fornecedor",
    description:
      "A JulIA prepara a lista de pendências e esclarecimentos de cada rodada e incorpora as respostas do fornecedor à análise, mantendo o histórico completo da negociação técnica.",
  },
  {
    number: "04",
    title: "Verificação final",
    description:
      "Antes do fechamento, uma conferência consolidada: o que foi resolvido, o que foi aceito com desvio e o que permanece em aberto.",
  },
  {
    number: "05",
    title: "Parecer técnico",
    description:
      "O documento final sai pronto para emissão. Cada conclusão aponta para a cláusula, a folha de dados ou a resposta do fornecedor que a sustenta.",
  },
]

const capabilities = [
  {
    icon: Table2,
    title: "Extração de dados técnicos",
    description:
      "Tabelas, folhas de dados e listas extraídas dos PDFs das propostas direto para a análise, sem redigitação.",
  },
  {
    icon: Library,
    title: "Base de conhecimento do projeto",
    description:
      "Especificações, normas e documentos de referência ficam consultáveis durante a análise, em workspace isolado por projeto.",
  },
  {
    icon: MessageSquareText,
    title: "Rastreabilidade de comentários",
    description:
      "Comentários de revisão em PDF são extraídos, organizados e vinculados ao histórico do caso.",
  },
  {
    icon: Languages,
    title: "Documentos bilíngues",
    description:
      "Análises e pareceres em português e espanhol, para projetos no Brasil e na Argentina.",
  },
]

const whyBlocks = [
  {
    title: "Metodologia embarcada, não chatbot",
    description:
      "O fluxo codifica a prática real de avaliação técnica em projetos EPC: instrumentação, automação, pacotes de fornecedores. A IA trabalha dentro de um processo de engenharia, não solta.",
  },
  {
    title: "Tudo verificável",
    description:
      "Nenhuma conclusão sem origem. Cada apontamento carrega a referência do documento que o sustenta, auditável por cliente e por fiscalização.",
  },
  {
    title: "O engenheiro assina, a plataforma prepara",
    description:
      "A responsabilidade técnica continua onde sempre esteve. A Noglem elimina o trabalho repetitivo, não o julgamento de engenharia.",
  },
]

const securityItems = [
  {
    lead: "Seus documentos não treinam modelos de IA.",
    text: "O processamento roda exclusivamente nas APIs corporativas pagas da OpenAI e do Google, cujos termos vedam o uso do conteúdo dos clientes para treinar ou melhorar modelos.",
  },
  {
    lead: "Isolamento por projeto e por cliente.",
    text: "Cada workspace é separado. Documentos de um projeto nunca alimentam a análise de outro.",
  },
  {
    lead: "Criptografia em trânsito e em repouso.",
    text: "Nos provedores e na plataforma.",
  },
  {
    lead: "NDA como parte do contrato.",
    text: "A confidencialidade é formalizada antes de qualquer documento ser carregado.",
  },
  {
    lead: "Controle de acesso e registro de atividade.",
    text: "Quem acessou o quê, quando.",
  },
]

export default async function HomePage() {
  const { userId } = await auth()

  if (userId) {
    redirect("/dashboard")
  }

  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <MarketingNav />

      <main className="flex-1 pt-16">
        {/* Hero */}
        <Section className="pt-12 sm:pt-16">
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <div className="space-y-6">
              <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
                Análise técnica de propostas, do requisito ao parecer final.
              </h1>
              <p className="max-w-xl text-lg leading-relaxed text-fg-muted">
                A Noglem conduz o ciclo completo de avaliação de propostas de fornecedores em
                projetos industriais: estrutura os requisitos, confronta cada proposta, prepara
                as rodadas de esclarecimento e emite o parecer final com cada conclusão ligada
                ao documento que a sustenta.
              </p>
              <div className="flex flex-wrap items-center gap-3">
                <Button size="lg" asChild>
                  <a href={site.demoHref}>Agendar demonstração</a>
                </Button>
                <Button size="lg" variant="outline" asChild>
                  <Link href="/#como-funciona">Ver como funciona</Link>
                </Button>
              </div>
            </div>
            <div className="flex justify-center lg:justify-end">
              <ParecerMock />
            </div>
          </div>
        </Section>

        {/* Barra de confiança */}
        <section aria-label="Compromissos de confiança" className="border-y border-edge bg-surface-1/50">
          <div className="container mx-auto px-4">
            <ul className="flex flex-col gap-2.5 py-5 sm:flex-row sm:items-center sm:justify-center sm:gap-10">
              {trustItems.map((item) => (
                <li key={item} className="flex items-center gap-2 text-sm text-fg-muted">
                  <ShieldCheck className="size-4 shrink-0 text-accent" aria-hidden="true" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* O problema */}
        <Section>
          <SectionHeading
            eyebrow="O problema"
            title="A equalização técnica é o gargalo silencioso do suprimento"
            description="Toda compra técnica relevante passa pelo mesmo funil: requisição, propostas, esclarecimentos, parecer. E o funil é manual. Engenheiros sênior passam dias cruzando folhas de dados contra especificações, proposta por proposta, planilha por planilha."
          />
          <div className="mt-10 grid gap-4 md:grid-cols-3">
            {painPoints.map((point) => (
              <Card key={point.title}>
                <CardContent className="space-y-2">
                  <h3 className="font-semibold tracking-tight">{point.title}</h3>
                  <p className="text-sm leading-relaxed text-fg-muted">{point.description}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </Section>

        {/* Como funciona */}
        <Section id="como-funciona" className="border-t border-edge">
          <SectionHeading
            eyebrow="Como funciona"
            title="Um ciclo completo, conduzido pela JulIA"
            description="JulIA é a agente de engenharia da Noglem. Ela executa cada etapa do caso técnico. O engenheiro revisa e decide."
          />
          <ol className="mt-10 max-w-3xl space-y-8">
            {steps.map((step) => (
              <li key={step.number} className="flex gap-5">
                <span className="pt-0.5 font-mono text-sm font-medium tabular-nums text-accent">
                  {step.number}
                </span>
                <div className="space-y-1.5">
                  <h3 className="font-semibold tracking-tight">{step.title}</h3>
                  <p className="text-sm leading-relaxed text-fg-muted">{step.description}</p>
                </div>
              </li>
            ))}
          </ol>
          <div className="mt-12 max-w-3xl rounded-r-sm border-l-2 border-accent bg-accent-subtle px-5 py-4">
            <p className="font-medium text-fg">
              Em todas as etapas, o engenheiro aprova antes de seguir. A JulIA não emite nada
              sozinha.
            </p>
          </div>
        </Section>

        {/* Capacidades da plataforma */}
        <Section id="plataforma" className="border-t border-edge">
          <SectionHeading eyebrow="Plataforma" title="O que trabalha por trás do parecer" />
          <div className="mt-10 grid gap-4 sm:grid-cols-2">
            {capabilities.map((capability) => (
              <Card key={capability.title}>
                <CardContent className="space-y-3">
                  <div className="flex size-9 items-center justify-center rounded-md bg-accent-subtle">
                    <capability.icon className="size-4.5 text-accent" aria-hidden="true" />
                  </div>
                  <h3 className="font-semibold tracking-tight">{capability.title}</h3>
                  <p className="text-sm leading-relaxed text-fg-muted">
                    {capability.description}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        </Section>

        {/* Por que a Noglem */}
        <Section className="border-t border-edge">
          <SectionHeading
            eyebrow="Por que a Noglem"
            title="Feita por quem passou 18 anos do outro lado da mesa"
          />
          <div className="mt-10 grid gap-8 md:grid-cols-3">
            {whyBlocks.map((block) => (
              <div key={block.title} className="space-y-2">
                <h3 className="font-semibold tracking-tight">{block.title}</h3>
                <p className="text-sm leading-relaxed text-fg-muted">{block.description}</p>
              </div>
            ))}
          </div>
          <p className="mt-10 max-w-3xl border-l-2 border-edge-strong pl-4 text-sm leading-relaxed text-fg-muted">
            Sem promessa de mágica: o ganho vem de processo estruturado e evidência rastreável,
            não de confiança cega no modelo.
          </p>
        </Section>

        {/* Segurança */}
        <Section id="seguranca" className="border-t border-edge">
          <SectionHeading
            eyebrow="Segurança"
            title="Documentos de projeto tratados como documentos de projeto"
          />
          <ul className="mt-10 max-w-3xl space-y-5">
            {securityItems.map((item) => (
              <li key={item.lead} className="text-sm leading-relaxed">
                <strong className="font-semibold text-fg">{item.lead}</strong>{" "}
                <span className="text-fg-muted">{item.text}</span>
              </li>
            ))}
          </ul>
          <Link
            href="/seguranca"
            className="mt-8 inline-flex items-center gap-1.5 text-sm text-accent hover:underline"
          >
            Ver detalhes de segurança e termos dos provedores
            <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        </Section>

        {/* Prova */}
        <section aria-label="Onde a Noglem é usada" className="border-y border-edge bg-surface-1/50">
          <div className="container mx-auto px-4 py-12">
            <p className="mx-auto max-w-2xl text-center text-lg leading-relaxed text-fg">
              Em uso na avaliação de propostas de pacotes de instrumentação e automação em
              projetos EPC no Brasil e na Argentina.
            </p>
          </div>
        </section>

        {/* Quem está por trás */}
        <Section id="quem-somos">
          <SectionHeading eyebrow="Quem somos" title="Quem está por trás" />
          <p className="mt-6 max-w-3xl leading-relaxed text-fg-muted">
            A Noglem é desenvolvida pela Fuchs Lemos Engenharia. Alexandre Nogueira Lemos,
            engenheiro de instrumentação e controle, atua há 18 anos em projetos EPC de óleo e
            gás, energia e mineração no Brasil e na Argentina. A plataforma nasceu dentro desses
            projetos, para resolver o trabalho que ele mesmo fazia à mão.
          </p>
          <a
            href={site.linkedinUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-6 inline-flex items-center gap-1.5 text-sm text-accent hover:underline"
          >
            LinkedIn
            <ArrowRight className="size-4" aria-hidden="true" />
          </a>
        </Section>

        {/* CTA final */}
        <Section className="border-t border-edge">
          <div className="mx-auto max-w-2xl space-y-6 text-center">
            <h2 className="text-2xl font-semibold tracking-tight sm:text-3xl">
              Veja a JulIA analisando uma proposta do seu projeto
            </h2>
            <p className="leading-relaxed text-fg-muted">
              Piloto com documentos reais, sob NDA. Você escolhe o pacote, nós rodamos o ciclo
              junto com a sua equipe.
            </p>
            <Button size="lg" asChild>
              <a href={site.demoHref}>Agendar demonstração</a>
            </Button>
          </div>
        </Section>
      </main>

      <MarketingFooter />
    </div>
  )
}
