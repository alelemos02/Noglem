import { NextRequest, NextResponse } from "next/server";
import { auth } from "@clerk/nextjs/server";
import { API_URL, buildBackendAuthHeaders } from "@/lib/backend";

// Catch-all route handler for RAG API
// Maps /api/rag/* to Backend /api/rag/*

async function handler(request: NextRequest, { params }: { params: { path: string[] } }) {
    try {
        const { userId } = await auth();
        if (!userId) {
            return NextResponse.json({ error: "Não autorizado" }, { status: 401 });
        }

        const path = params.path.join("/");
        const url = `${API_URL}/api/rag/${path}`;
        const searchParams = request.nextUrl.searchParams.toString();
        const finalUrl = searchParams ? `${url}?${searchParams}` : url;

        // Headers
        const headers = buildBackendAuthHeaders(userId);

        // Content-Type handling for FormData/JSON
        const contentType = request.headers.get("content-type");
        if (contentType) {
            if (!contentType.includes("multipart/form-data")) {
                headers["Content-Type"] = contentType;
            }
            // If multipart, do NOT set Content-Type header, fetch will set it with boundary automatically 
            // IF we pass FormData directly. But we are reading as blob/arrayBuffer or passing body stream?
            // NextJS Request body is a stream. We can pass it directly?
        }

        const options: RequestInit = {
            method: request.method,
            headers: headers,
            // Default body handling
            body: request.body,
            // Important for streaming responses if backend streams (like chat)
            // duplex: 'half' is required for streaming uploads in some fetch implementations, 
            // but here we are streaming passing through.
        };

        // Special handling for FormData if needed, but usually passing request.body works if we don't consume it.
        // However, NextRequest body might be consumed already?

        // Let's rely on standard fetch behavior with body stream.

        const response = await fetch(finalUrl, options);

        // Handle Streaming Responses (SSE)
        if (response.headers.get("content-type")?.includes("text/event-stream")) {
            return new NextResponse(response.body, {
                headers: {
                    "Content-Type": "text/event-stream",
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                }
            });
        }

        // Handle File Downloads (PDF)
        if (response.headers.get("content-type")?.includes("application/pdf")) {
            return new NextResponse(response.body, {
                headers: {
                    "Content-Type": "application/pdf",
                    "Content-Disposition": response.headers.get("Content-Disposition") || "inline",
                }
            });
        }

        // Standard JSON Response
        if (!response.ok) {
            const errorText = await response.text();
            try {
                const errorJson = JSON.parse(errorText);
                return NextResponse.json(errorJson, { status: response.status });
            } catch {
                return NextResponse.json({ detail: errorText }, { status: response.status });
            }
        }

        // If 204 No Content
        if (response.status === 204) {
            return new NextResponse(null, { status: 204 });
        }

        const data = await response.json();
        return NextResponse.json(data);

    } catch (error) {
        console.error(`Proxy Error [${request.method} /api/rag/${params.path.join("/")}]:`, error);
        return NextResponse.json(
            { error: "Erro de comunicação com o backend." },
            { status: 503 }
        );
    }
}

export { handler as GET, handler as POST, handler as PUT, handler as DELETE };
