/**
 * Constantes do site público Noglem (landing + páginas institucionais).
 * Ponto único para trocar e-mail comercial, links e dados legais.
 */

type NavLink = {
  label: string
  href: string
}

type SiteConfig = {
  name: string
  url: string
  title: string
  description: string
  demoEmail: string
  demoHref: string
  linkedinUrl: string
  legalName: string
  /** Preencher antes do lançamento — vazio não é renderizado no rodapé */
  cnpj: string
  /** Preencher antes do lançamento — vazio não é renderizado no rodapé */
  crea: string
  navLinks: NavLink[]
}

export const site: SiteConfig = {
  name: "Noglem",
  url: "https://www.noglem.com.br",
  title: "Noglem — Análise técnica de propostas",
  description:
    "A Noglem conduz o ciclo completo de avaliação de propostas de fornecedores em projetos industriais: estrutura os requisitos, confronta cada proposta, prepara as rodadas de esclarecimento e emite o parecer final com rastreabilidade total.",
  demoEmail: "alelemos02@gmail.com",
  demoHref: "mailto:alelemos02@gmail.com?subject=Demonstra%C3%A7%C3%A3o%20Noglem",
  linkedinUrl: "https://www.linkedin.com/in/alexandre-nogueira-lemos",
  legalName: "Fuchs Lemos Engenharia Ltda",
  cnpj: "",
  crea: "",
  navLinks: [
    { label: "Como funciona", href: "/#como-funciona" },
    { label: "Plataforma", href: "/#plataforma" },
    { label: "Segurança", href: "/#seguranca" },
    { label: "Quem somos", href: "/#quem-somos" },
  ],
}
