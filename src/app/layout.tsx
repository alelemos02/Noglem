import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { ptBR } from "@clerk/localizations";
import { Suspense } from "react";
import { PostHogProvider } from "@/components/posthog-provider";
import { fontSans, fontMono } from "@/lib/fonts";
import "./globals.css";

const fontVariables = `${fontSans.variable} ${fontMono.variable}`;

// Appearance do Clerk alinhada aos tokens do design system
// (o popup do UserButton renderiza dentro do dashboard)
const clerkAppearance = {
  variables: {
    colorBackground: "#17181D",
    colorInputBackground: "#1C1E25",
    colorText: "#E9EBEF",
    colorTextSecondary: "#A3A9B5",
    colorPrimary: "#4BA4EE",
    colorDanger: "#EF5F52",
    colorSuccess: "#43C583",
    colorWarning: "#DFB13F",
    colorNeutral: "#E9EBEF",
    borderRadius: "6px",
    fontFamily: "var(--font-plex-sans), system-ui, sans-serif",
  },
};

export const metadata: Metadata = {
  title: "Jul/IA - Engineering Intelligence",
  description: "Plataforma centralizada de agentes de IA para engenharia - Tradução AI, Extração de PDFs, Análise e Conversão de documentos",
  keywords: ["engenharia", "agentes", "agentes de ia", "ferramentas", "pdf", "tradução", "IA", "documentos"],
};

const isClerkConfigured =
  process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY &&
  !process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY.includes("YOUR_KEY_HERE");

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  if (!isClerkConfigured) {
    return (
      <html lang="pt-BR" className={fontVariables}>
        <body className="font-sans antialiased">
          <div className="flex min-h-screen items-center justify-center bg-canvas p-8">
            <div className="max-w-md space-y-6 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-lg bg-warning-subtle">
                <svg className="h-8 w-8 text-warning" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <h1 className="text-2xl font-bold">Configuração Necessária</h1>
              <p className="text-fg-muted">
                Para usar o Jul/IA, você precisa configurar as chaves do Clerk.
              </p>
              <div className="rounded-lg border border-edge bg-surface-2 p-4 text-left text-sm">
                <p className="mb-2 font-medium">Passos:</p>
                <ol className="list-inside list-decimal space-y-1 text-fg-muted">
                  <li>Crie uma conta em <a href="https://clerk.com" target="_blank" rel="noopener" className="text-accent hover:underline">clerk.com</a></li>
                  <li>Crie uma nova aplicação</li>
                  <li>Copie as chaves do dashboard</li>
                  <li>Atualize o arquivo <code className="rounded bg-canvas px-1 font-mono">.env.local</code></li>
                  <li>Reinicie o servidor de desenvolvimento</li>
                </ol>
              </div>
            </div>
          </div>
        </body>
      </html>
    );
  }

  return (
    <ClerkProvider localization={ptBR} appearance={clerkAppearance}>
      <html lang="pt-BR" className={fontVariables}>
        <body className="font-sans antialiased">
          <Suspense fallback={null}>
            <PostHogProvider>{children}</PostHogProvider>
          </Suspense>
        </body>
      </html>
    </ClerkProvider>
  );
}
