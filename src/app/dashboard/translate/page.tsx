"use client";

import { useState } from "react";
import { Languages, ArrowRight, Copy, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const languages = [
  { code: "pt", name: "Português" },
  { code: "en", name: "Inglês" },
  { code: "es", name: "Espanhol" },
  { code: "fr", name: "Francês" },
  { code: "de", name: "Alemão" },
  { code: "it", name: "Italiano" },
  { code: "zh", name: "Chinês" },
  { code: "ja", name: "Japonês" },
];

export default function TranslatePage() {
  const [sourceText, setSourceText] = useState("");
  const [translatedText, setTranslatedText] = useState("");
  const [sourceLang, setSourceLang] = useState("pt");
  const [targetLang, setTargetLang] = useState("en");
  const [isLoading, setIsLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");

  const handleTranslate = async () => {
    if (!sourceText.trim()) return;

    setIsLoading(true);
    setError("");
    try {
      const response = await fetch("/api/translate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: sourceText,
          source_lang: sourceLang,
          target_lang: targetLang,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Erro na tradução");
      }

      setTranslatedText(data.translated_text);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Erro desconhecido";
      setError(message);
      console.error("Erro na tradução:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(translatedText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-500/10">
          <Languages className="h-6 w-6 text-blue-500" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Tradutor AI</h1>
          <p className="text-muted-foreground">
            Traduza textos técnicos com precisão usando Google Gemini
          </p>
        </div>
        <Badge className="ml-auto">Live</Badge>
      </div>

      {/* Translation Interface */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Source */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Texto Original</CardTitle>
              <select
                value={sourceLang}
                onChange={(e) => setSourceLang(e.target.value)}
                className="rounded-md border border-input bg-background px-3 py-1 text-sm"
              >
                {languages.map((lang) => (
                  <option key={lang.code} value={lang.code}>
                    {lang.name}
                  </option>
                ))}
              </select>
            </div>
          </CardHeader>
          <CardContent>
            <textarea
              value={sourceText}
              onChange={(e) => setSourceText(e.target.value)}
              placeholder="Digite ou cole o texto para traduzir..."
              className="min-h-[200px] w-full resize-none rounded-md border border-input bg-background p-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </CardContent>
        </Card>

        {/* Target */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Tradução</CardTitle>
              <select
                value={targetLang}
                onChange={(e) => setTargetLang(e.target.value)}
                className="rounded-md border border-input bg-background px-3 py-1 text-sm"
              >
                {languages.map((lang) => (
                  <option key={lang.code} value={lang.code}>
                    {lang.name}
                  </option>
                ))}
              </select>
            </div>
          </CardHeader>
          <CardContent>
            <div className="relative">
              <textarea
                value={translatedText}
                readOnly
                placeholder="A tradução aparecerá aqui..."
                className="min-h-[200px] w-full resize-none rounded-md border border-input bg-muted/50 p-3 text-sm"
              />
              {translatedText && (
                <Button
                  size="icon"
                  variant="ghost"
                  className="absolute right-2 top-2"
                  onClick={handleCopy}
                >
                  {copied ? (
                    <Check className="h-4 w-4 text-green-500" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Error Message */}
      {error && (
        <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-4 text-center text-sm text-red-500">
          {error}
        </div>
      )}

      {/* Action Button */}
      <div className="flex justify-center">
        <Button
          size="lg"
          onClick={handleTranslate}
          disabled={!sourceText.trim() || isLoading}
          className="gap-2"
        >
          {isLoading ? (
            <>
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
              Traduzindo...
            </>
          ) : (
            <>
              Traduzir
              <ArrowRight className="h-4 w-4" />
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
