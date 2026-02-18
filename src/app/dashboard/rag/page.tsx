"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Folder, Trash2, Search, ArrowRight, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
  SheetFooter,
  SheetClose,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";

interface Collection {
  id: string;
  name: string;
  created_at: string;
  documents: any[]; // We might load documents count
}

export default function RagDashboard() {
  const router = useRouter();
  const [collections, setCollections] = useState<Collection[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");

  // Create Collection State
  const [newCollectionName, setNewCollectionName] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [isSheetOpen, setIsSheetOpen] = useState(false);

  useEffect(() => {
    fetchCollections();
  }, []);

  const fetchCollections = async () => {
    try {
      const res = await fetch("/api/rag/collections");
      if (res.ok) {
        const data = await res.json();
        setCollections(data);
      }
    } catch (error) {
      console.error("Failed to fetch collections", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateCollection = async () => {
    if (!newCollectionName.trim()) return;

    setIsCreating(true);
    try {
      const res = await fetch("/api/rag/collections", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newCollectionName }),
      });

      if (res.ok) {
        fetchCollections();
        setNewCollectionName("");
        setIsSheetOpen(false);
      }
    } catch (error) {
      console.error("Error creating collection", error);
    } finally {
      setIsCreating(false);
    }
  };

  const handleDeleteCollection = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent opening collection
    if (!confirm("Tem certeza que deseja excluir esta coleção e todos os seus documentos?")) return;

    try {
      const res = await fetch(`/api/rag/collections/${id}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setCollections(collections.filter((c) => c.id !== id));
      }
    } catch (error) {
      console.error("Error deleting collection", error);
    }
  };

  const filteredCollections = collections.filter(c =>
    c.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="flex flex-col space-y-8 p-8 h-full bg-background/50">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Base de Conhecimento (RAG)</h1>
          <p className="text-muted-foreground mt-2">
            Gerencie suas coleções de documentos e converse com elas usando IA.
          </p>
        </div>

        <Sheet open={isSheetOpen} onOpenChange={setIsSheetOpen}>
          <SheetTrigger asChild>
            <Button size="lg" className="shadow-sm">
              <Plus className="mr-2 h-4 w-4" /> Nova Coleção
            </Button>
          </SheetTrigger>
          <SheetContent>
            <SheetHeader>
              <SheetTitle>Criar Nova Coleção</SheetTitle>
              <SheetDescription>
                Dê um nome para sua coleção de documentos. Você poderá adicionar PDFs depois.
              </SheetDescription>
            </SheetHeader>
            <div className="grid gap-4 py-4">
              <div className="grid gap-2">
                <Input
                  id="name"
                  placeholder="Ex: Manuais de Engenharia, Normas ISO..."
                  value={newCollectionName}
                  onChange={(e) => setNewCollectionName(e.target.value)}
                />
              </div>
            </div>
            <SheetFooter>
              <SheetClose asChild>
                <Button variant="outline">Cancelar</Button>
              </SheetClose>
              <Button onClick={handleCreateCollection} disabled={isCreating || !newCollectionName}>
                {isCreating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Criar Coleção
              </Button>
            </SheetFooter>
          </SheetContent>
        </Sheet>
      </div>

      {/* Search and Content */}
      <div className="flex flex-col gap-6">
        <div className="relative w-full max-w-sm">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Buscar coleções..."
            className="pl-9"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        {isLoading ? (
          <div className="flex h-64 w-full items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
          </div>
        ) : filteredCollections.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-16 text-center animate-in fade-in-50">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted/50">
              <Folder className="h-8 w-8 text-muted-foreground" />
            </div>
            <h3 className="mt-4 text-lg font-semibold">Nenhuma coleção encontrada</h3>
            <p className="mb-4 text-sm text-muted-foreground max-w-sm">
              Você ainda não criou nenhuma coleção de conhecimento. Comece criando uma para organizar seus documentos.
            </p>
            <Button variant="outline" onClick={() => setIsSheetOpen(true)}>
              Criar Primeira Coleção
            </Button>
          </div>
        ) : (
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {filteredCollections.map((collection) => (
              <Card
                key={collection.id}
                className="group relative cursor-pointer overflow-hidden transition-all hover:shadow-md border-muted-foreground/10 hover:border-primary/50 bg-card"
                onClick={() => router.push(`/dashboard/rag/${collection.id}`)}
              >
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 transition-colors group-hover:bg-primary/20">
                      <Folder className="h-5 w-5 text-primary" />
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 hover:text-destructive hover:bg-destructive/10"
                      onClick={(e) => handleDeleteCollection(collection.id, e)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                  <CardTitle className="mt-3 text-lg font-semibold leading-none tracking-tight">
                    {collection.name}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center text-sm text-muted-foreground">
                    <span className="truncate">
                      Criado em {new Date(collection.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </CardContent>
                <CardFooter className="pt-0">
                  <div className="flex w-full items-center justify-between text-xs text-muted-foreground opacity-60 transition-opacity group-hover:opacity-100">
                    <Badge variant="secondary" className="font-normal text-xs pointer-events-none">
                      Privado
                    </Badge>
                    <span className="flex items-center gap-1">
                      Abrir <ArrowRight className="h-3 w-3" />
                    </span>
                  </div>
                </CardFooter>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
