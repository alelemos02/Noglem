"use client";

import { useState } from "react";
import { ArrowRight, Copy, Check, Sparkles, Globe, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/page-header";
import { Textarea } from "@/components/ui/textarea";
import { Alert } from "@/components/ui/alert";
import { toast } from "@/components/ui/toast";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

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

function LangPill({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "rounded-sm px-2.5 py-1 font-mono text-[11px] uppercase tracking-wide transition-colors",
        active
          ? "bg-surface-3 font-medium text-fg"
          : "text-fg-subtle hover:bg-surface-2 hover:text-fg"
      )}
    >
      {children}
    </button>
  );
}

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

  const handleClear = () => {
    setSourceText("");
    setTranslatedText("");
    setImprovedText("");
    setDetectedLang("");
    setError("");
  };

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
      toast.success("Tradução concluída");

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
    toast.success("Copiado para a área de transferência");
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6">
      <PageHeader tool="translate" />

      {/* Controls */}
      <Card className="gap-0 py-0">
        <CardContent className="flex items-center justify-between gap-4 p-4">
          <div className="flex items-center gap-3">
            <Sparkles className={`h-5 w-5 shrink-0 ${improveMode ? "text-warning" : "text-fg-subtle"}`} />
            <div>
              <h3 className="text-sm font-semibold text-fg">Melhorar texto</h3>
              <p className="text-[13px] text-fg-muted">Reescreve o texto original para maior fluidez antes de traduzir.</p>
            </div>
          </div>
          <label className="relative inline-flex cursor-pointer items-center">
            <input
              type="checkbox"
              className="peer sr-only"
              checked={improveMode}
              onChange={(e) => setImproveMode(e.target.checked)}
            />
            <div className="peer h-5 w-9 rounded-full bg-surface-3 border border-edge-strong after:absolute after:left-[3px] after:top-[3px] after:h-[14px] after:w-[14px] after:rounded-full after:bg-fg-muted after:transition-all after:content-[''] peer-checked:bg-accent peer-checked:border-accent peer-checked:after:translate-x-4 peer-checked:after:bg-accent-fg peer-focus-visible:outline-none peer-focus-visible:ring-2 peer-focus-visible:ring-accent peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-canvas"></div>
          </label>
        </CardContent>
      </Card>

      {/* Translation Interface */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Source */}
        <Card className="flex h-full flex-col gap-4">
          <CardHeader className="pb-0">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle className="flex items-center gap-2 text-sm">
                Texto original
                {detectedLang && (
                  <span className="flex items-center gap-1 rounded-sm bg-surface-2 px-2 py-0.5 font-mono text-[10px] font-normal uppercase tracking-wide text-fg-muted">
                    <Globe className="h-3 w-3" /> {detectedLang}
                  </span>
                )}
              </CardTitle>
              <div className="flex items-center gap-2">
                <div className="hidden items-center gap-0.5 rounded-md border border-edge bg-surface-2/50 p-0.5 sm:flex">
                  <LangPill active={sourceLang === "auto"} onClick={() => setSourceLang("auto")}>Auto</LangPill>
                  <LangPill active={sourceLang === "pt"} onClick={() => setSourceLang("pt")}>PT</LangPill>
                  <LangPill active={sourceLang === "en"} onClick={() => setSourceLang("en")}>EN</LangPill>
                  <LangPill active={sourceLang === "es"} onClick={() => setSourceLang("es")}>ES</LangPill>
                </div>
                <Select value={sourceLang} onValueChange={setSourceLang}>
                  <SelectTrigger className="h-8 w-[150px] text-[13px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="auto">Detectar idioma</SelectItem>
                    {languages.map((lang) => (
                      <SelectItem key={lang.code} value={lang.code}>
                        {lang.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardHeader>
          <CardContent className="flex-1">
            <Textarea
              value={sourceText}
              onChange={(e) => setSourceText(e.target.value)}
              placeholder="Digite ou cole o texto para traduzir..."
              className="min-h-[300px] resize-none"
            />
          </CardContent>
        </Card>

        {/* Target */}
        <Card className="flex h-full flex-col gap-4">
          <CardHeader className="pb-0">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle className="text-sm">Tradução</CardTitle>
              <div className="flex items-center gap-2">
                <div className="hidden items-center gap-0.5 rounded-md border border-edge bg-surface-2/50 p-0.5 sm:flex">
                  <LangPill active={targetLang === "pt"} onClick={() => setTargetLang("pt")}>PT</LangPill>
                  <LangPill active={targetLang === "en"} onClick={() => setTargetLang("en")}>EN</LangPill>
                  <LangPill active={targetLang === "es"} onClick={() => setTargetLang("es")}>ES</LangPill>
                </div>
                <Select value={targetLang} onValueChange={setTargetLang}>
                  <SelectTrigger className="h-8 w-[150px] text-[13px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {languages.map((lang) => (
                      <SelectItem key={lang.code} value={lang.code}>
                        {lang.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardHeader>
          <CardContent className="flex-1 space-y-4">

            {/* Improved Text Section (Optional) */}
            {improveMode && improvedText && (
              <Alert variant="warning" title="Texto melhorado (original refinado)" icon={Sparkles}>
                <p className="italic">{improvedText}</p>
              </Alert>
            )}

            <div className="relative h-full flex-1">
              <Textarea
                value={translatedText}
                readOnly
                placeholder="A tradução aparecerá aqui..."
                className={`resize-none bg-surface-1 ${improveMode && improvedText ? "min-h-[220px]" : "min-h-[300px]"}`}
              />
              {translatedText && (
                <Button
                  size="icon"
                  variant="ghost"
                  className="absolute right-2 top-2"
                  onClick={() => handleCopy(translatedText)}
                >
                  {copied ? (
                    <Check className="h-4 w-4 text-success" />
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
      {error && <Alert variant="danger">{error}</Alert>}

      {/* Action Button */}
      <div className="flex justify-center gap-4">
        <Button
          size="lg"
          variant="outline"
          onClick={handleClear}
          disabled={!sourceText && !translatedText}
          className="min-w-[120px] gap-2"
        >
          <Trash2 className="h-4 w-4" />
          Limpar
        </Button>
        <Button
          size="lg"
          onClick={handleTranslate}
          disabled={!sourceText.trim()}
          loading={isLoading}
          className="min-w-[200px] gap-2"
        >
          {isLoading ? (
            "Traduzindo..."
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
