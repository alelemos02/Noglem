"use client";

import { useState } from "react";
import { Languages, ArrowRight, Copy, Check, Sparkles, Globe } from "lucide-react";
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
  { code: "ru", name: "Russo" },
  { code: "ar", name: "Árabe" },
];

export default function TranslatePage() {
  const [sourceText, setSourceText] = useState("");
  const [translatedText, setTranslatedText] = useState("");
  const [improvedText, setImprovedText] = useState("");
  const [detectedLang, setDetectedLang] = useState("");
  const [sourceLang, setSourceLang] = useState("pt");
  const [targetLang, setTargetLang] = useState("en");
  const [improveMode, setImproveMode] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");

  const handleTranslate = async () => {
    if (!sourceText.trim()) return;

    setIsLoading(true);
    setError("");
    setTranslatedText("");
    setImprovedText("");
    setDetectedLang("");

    try {
      const response = await fetch("/api/translate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: sourceText,
          source_lang: sourceLang,
          target_lang: targetLang,
          improve_mode: improveMode,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Erro na tradução");
      }

      setTranslatedText(data.translated_text);
      if (data.improved_text) setImprovedText(data.improved_text);
      if (data.detected_language) setDetectedLang(data.detected_language);

    } catch (err) {
      const message = err instanceof Error ? err.message : "Erro desconhecido";
      setError(message);
      console.error("Erro na tradução:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
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

      {/* Controls */}
      <div className="flex items-center justify-between rounded-lg border bg-card p-4 shadow-sm">
        <div className="flex items-center gap-3">
          <Sparkles className={`h-5 w-5 ${improveMode ? "text-amber-500" : "text-muted-foreground"}`} />
          <div>
            <h3 className="font-medium text-sm">Modo de Melhoria (Improve Mode)</h3>
            <p className="text-xs text-muted-foreground">Reescreve o texto original para maior fluidez antes de traduzir.</p>
          </div>
        </div>
        <label className="relative inline-flex cursor-pointer items-center">
          <input
            type="checkbox"
            className="peer sr-only"
            checked={improveMode}
            onChange={(e) => setImproveMode(e.target.checked)}
          />
          <div className="peer h-6 w-11 rounded-full bg-input after:absolute after:left-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:bg-background after:transition-all after:content-[''] peer-checked:bg-blue-600 peer-checked:after:translate-x-full peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-ring peer-focus:ring-offset-2"></div>
        </label>
      </div>

      {/* Translation Interface */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Source */}
        <Card className="flex flex-col h-full">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                Texto Original
                {detectedLang && (
                  <span className="flex items-center gap-1 text-xs font-normal text-muted-foreground bg-muted px-2 py-0.5 rounded-full">
                    <Globe className="h-3 w-3" /> Detectado: {detectedLang}
                  </span>
                )}
              </CardTitle>
              <select
                value={sourceLang}
                onChange={(e) => setSourceLang(e.target.value)}
                className="rounded-md border border-input bg-background px-3 py-1 text-sm"
              >
                <option value="auto">Detectar Idioma</option>
                {languages.map((lang) => (
                  <option key={lang.code} value={lang.code}>
                    {lang.name}
                  </option>
                ))}
              </select>
            </div>
          </CardHeader>
          <CardContent className="flex-1">
            <textarea
              value={sourceText}
              onChange={(e) => setSourceText(e.target.value)}
              placeholder="Digite ou cole o texto para traduzir..."
              className="min-h-[300px] w-full resize-none rounded-md border border-input bg-background p-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </CardContent>
        </Card>

        {/* Target */}
        <Card className="flex flex-col h-full">
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
          <CardContent className="flex-1 space-y-4">

            {/* Improved Text Section (Optional) */}
            {improveMode && improvedText && (
              <div className="rounded-md border border-amber-500/20 bg-amber-500/5 p-3">
                <p className="mb-1 text-xs font-semibold text-amber-600 flex items-center gap-1">
                  <Sparkles className="h-3 w-3" /> Texto Melhorado (Original Refinado):
                </p>
                <p className="text-sm text-foreground/90 italic">{improvedText}</p>
              </div>
            )}

            <div className="relative flex-1 h-full">
              <textarea
                value={translatedText}
                readOnly
                placeholder="A tradução aparecerá aqui..."
                className={`w-full resize-none rounded-md border border-input bg-muted/50 p-3 text-sm ${improveMode && improvedText ? 'min-h-[220px]' : 'min-h-[300px]'}`}
              />
              {translatedText && (
                <Button
                  size="icon"
                  variant="ghost"
                  className="absolute right-2 top-2"
                  onClick={() => handleCopy(translatedText)}
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
          className="gap-2 min-w-[200px]"
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
