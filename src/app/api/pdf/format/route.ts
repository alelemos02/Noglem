import { NextRequest, NextResponse } from "next/server";
import { auth } from "@clerk/nextjs/server";
import { API_URL, buildBackendAuthHeaders } from "@/lib/backend";

export async function POST(request: NextRequest) {
    try {
        const { userId } = await auth();
        if (!userId) {
            return NextResponse.json({ error: "Não autorizado" }, { status: 401 });
        }

        const formData = await request.formData();

        const response = await fetch(`${API_URL}/api/pdf/format`, {
            method: "POST",
            headers: buildBackendAuthHeaders(userId),
            body: formData,
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: "Erro no servidor" }));
            return NextResponse.json(
                { error: error.detail || "Erro na formatação" },
                { status: response.status }
            );
        }

        const data = await response.json();
        return NextResponse.json(data);
    } catch (error) {
        console.error("Erro ao conectar com backend:", error);
        return NextResponse.json(
            { error: "Backend indisponível. Verifique se o servidor está rodando." },
            { status: 503 }
        );
    }
}
