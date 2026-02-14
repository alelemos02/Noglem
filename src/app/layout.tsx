import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { ClerkProvider } from "@clerk/nextjs";
import { ptBR } from "@clerk/localizations";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Julia - Portal de Engenharia",
  description: "Plataforma centralizada de ferramentas de engenharia - Tradução AI, Extração de PDFs e Conversão de documentos",
  keywords: ["engenharia", "ferramentas", "pdf", "tradução", "IA", "documentos"],
};

// Verificar se as chaves do Clerk estão configuradas
const isClerkConfigured =
  process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY &&
  !process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY.includes("YOUR_KEY_HERE");

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Se Clerk não está configurado, renderizar sem auth
  if (!isClerkConfigured) {
    return (
      <html lang="pt-BR" className="dark">
        <body className={`${inter.variable} font-sans antialiased`}>
          <div className="flex min-h-screen items-center justify-center bg-background p-8">
            <div className="max-w-md space-y-6 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-yellow-500/10">
                <svg className="h-8 w-8 text-yellow-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <h1 className="text-2xl font-bold">Configuração Necessária</h1>
              <p className="text-muted-foreground">
                Para usar o Julia, você precisa configurar as chaves do Clerk.
              </p>
              <div className="rounded-lg border border-border bg-muted p-4 text-left text-sm">
                <p className="mb-2 font-medium">Passos:</p>
                <ol className="list-inside list-decimal space-y-1 text-muted-foreground">
                  <li>Crie uma conta em <a href="https://clerk.com" target="_blank" rel="noopener" className="text-primary hover:underline">clerk.com</a></li>
                  <li>Crie uma nova aplicação</li>
                  <li>Copie as chaves do dashboard</li>
                  <li>Atualize o arquivo <code className="rounded bg-background px-1">.env.local</code></li>
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
    <ClerkProvider localization={ptBR}>
      <html lang="pt-BR" className="dark">
        <body className={`${inter.variable} font-sans antialiased`}>
          {children}
        </body>
      </html>
    </ClerkProvider>
  );
}
