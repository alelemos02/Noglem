"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertCircle, CheckCircle2, Loader2, ArrowLeft } from "lucide-react";
import Link from "next/link";

export default function VerifyInvitePage() {
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const router = useRouter();

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/validate/${code.toUpperCase()}`);
      const data = await response.json();

      if (response.ok && data.valid) {
        setSuccess(true);
        // Set cookie (primitive version for simplicity in this step)
        document.cookie = `invite_code=${code.toUpperCase()}; path=/; max-age=3600; SameSite=Lax`;
        
        setTimeout(() => {
          router.push("/sign-up");
        }, 1500);
      } else {
        setError(data.detail || "Código de convite inválido ou já utilizado.");
      }
    } catch (err) {
      setError("Erro ao conectar com o servidor. Tente novamente mais tarde.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-md space-y-4">
        <Link href="/" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors">
          <ArrowLeft className="h-4 w-4" />
          Voltar para Home
        </Link>
        
        <Card className="border-border shadow-xl">
          <CardHeader className="space-y-1">
            <CardTitle className="text-2xl font-bold text-center">Acesso Restrito</CardTitle>
            <CardDescription className="text-center">
              O Jul/IA está em beta privado. Insira seu código de convite para continuar.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleVerify} className="space-y-4">
              <div className="space-y-2">
                <Input
                  placeholder="DIGITE SEU CÓDIGO"
                  value={code}
                  onChange={(e) => setCode(e.target.value.toUpperCase())}
                  className="text-center text-lg font-mono tracking-widest uppercase h-12"
                  disabled={loading || success}
                  autoFocus
                />
              </div>

              {error && (
                <div className="flex items-center gap-2 rounded-lg bg-destructive/10 p-3 text-sm text-destructive border border-destructive/20">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  <p>{error}</p>
                </div>
              )}

              {success && (
                <div className="flex items-center gap-2 rounded-lg bg-success/10 p-3 text-sm text-success border border-success/20">
                  <CheckCircle2 className="h-4 w-4 shrink-0" />
                  <p>Código validado! Redirecionando...</p>
                </div>
              )}

              <Button 
                type="submit" 
                className="w-full h-12 text-lg font-semibold bg-accent hover:bg-accent/90"
                disabled={loading || success || !code}
              >
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Validando...
                  </>
                ) : "Acessar Plataforma"}
              </Button>
            </form>
          </CardContent>
          <CardFooter className="flex flex-col gap-4 border-t border-border pt-6 mt-2">
            <p className="text-xs text-center text-muted-foreground">
              Não tem um convite? Siga-nos para saber quando novas vagas forem abertas.
            </p>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
}
