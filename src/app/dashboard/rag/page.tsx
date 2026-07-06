"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Folder, Trash2, Search, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
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
import { PageHeader } from "@/components/ui/page-header";
import { LoadingBlock } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { toast } from "@/components/ui/toast";
import { useConfirm } from "@/components/ui/confirm-dialog";

interface Collection {
  id: string;
  name: string;
  created_at: string;
  documents: unknown[];
}

export default function RagDashboard() {
  const router = useRouter();
  const confirm = useConfirm();
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
      toast.error("Erro ao carregar coleções");
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
        toast.success("Coleção criada", { description: newCollectionName });
        setNewCollectionName("");
        setIsSheetOpen(false);
      } else {
        toast.error("Erro ao criar coleção");
      }
    } catch (error) {
      console.error("Error creating collection", error);
      toast.error("Erro ao criar coleção");
    } finally {
      setIsCreating(false);
    }
  };

  const handleDeleteCollection = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent opening collection
    const name = collections.find((c) => c.id === id)?.name;
    const ok = await confirm({
      title: "Excluir coleção?",
      description: `"${name ?? "Esta coleção"}" e todos os seus documentos serão removidos permanentemente.`,
      confirmLabel: "Excluir coleção",
      variant: "danger",
    });
    if (!ok) return;

    try {
      const res = await fetch(`/api/rag/collections/${id}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setCollections(collections.filter((c) => c.id !== id));
        toast.success("Coleção excluída");
      } else {
        toast.error("Erro ao excluir coleção");
      }
    } catch (error) {
      console.error("Error deleting collection", error);
      toast.error("Erro ao excluir coleção");
    }
  };

  const filteredCollections = collections.filter(c =>
    c.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="flex flex-col space-y-6">
      <PageHeader
        tool="rag"
        actions={
          <Sheet open={isSheetOpen} onOpenChange={setIsSheetOpen}>
            <SheetTrigger asChild>
              <Button>
                <Plus className="h-4 w-4" /> Nova coleção
              </Button>
            </SheetTrigger>
            <SheetContent>
              <SheetHeader>
                <SheetTitle>Criar nova coleção</SheetTitle>
                <SheetDescription>
                  Dê um nome para sua coleção de documentos. Você poderá adicionar PDFs depois.
                </SheetDescription>
              </SheetHeader>
              <div className="grid gap-4 px-4 py-2">
                <Input
                  id="name"
                  placeholder="Ex: Manuais de Engenharia, Normas ISO..."
                  value={newCollectionName}
                  onChange={(e) => setNewCollectionName(e.target.value)}
                />
              </div>
              <SheetFooter>
                <SheetClose asChild>
                  <Button variant="outline">Cancelar</Button>
                </SheetClose>
                <Button
                  onClick={handleCreateCollection}
                  disabled={!newCollectionName}
                  loading={isCreating}
                >
                  Criar coleção
                </Button>
              </SheetFooter>
            </SheetContent>
          </Sheet>
        }
      />

      {/* Search and Content */}
      <div className="flex flex-col gap-6">
        <div className="relative w-full max-w-sm">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-fg-subtle" />
          <Input
            type="search"
            placeholder="Buscar coleções..."
            className="pl-9"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        {isLoading ? (
          <LoadingBlock label="Carregando coleções..." />
        ) : filteredCollections.length === 0 ? (
          <EmptyState
            icon={Folder}
            title="Nenhuma coleção encontrada"
            description="Você ainda não criou nenhuma coleção de conhecimento. Comece criando uma para organizar seus documentos."
            action={
              <Button variant="outline" onClick={() => setIsSheetOpen(true)}>
                Criar primeira coleção
              </Button>
            }
          />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {filteredCollections.map((collection) => (
              <Card
                key={collection.id}
                interactive
                className="group relative gap-3 py-4"
                onClick={() => router.push(`/dashboard/rag/${collection.id}`)}
              >
                <CardHeader className="pb-0">
                  <div className="flex items-start justify-between">
                    <Folder className="h-5 w-5 text-fg-subtle transition-colors group-hover:text-accent" />
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      className="text-fg-subtle opacity-0 transition-opacity hover:bg-danger-subtle hover:text-danger group-hover:opacity-100"
                      onClick={(e) => handleDeleteCollection(collection.id, e)}
                      title="Excluir coleção"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                  <CardTitle className="mt-2 text-sm font-semibold leading-tight">
                    {collection.name}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="truncate font-mono text-[11px] tabular-nums text-fg-subtle">
                    Criado em {new Date(collection.created_at).toLocaleDateString()}
                  </p>
                </CardContent>
                <CardFooter className="pt-0">
                  <div className="flex w-full items-center justify-between text-xs text-fg-muted opacity-60 transition-opacity group-hover:opacity-100">
                    <Badge variant="secondary" className="pointer-events-none px-1.5 py-0 text-[9px]">
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
