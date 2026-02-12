/**
 * Shared backend configuration/helpers for server-side routes.
 */
export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function buildBackendAuthHeaders(userId: string, includeJsonContentType = false): HeadersInit {
  const internalApiKey = process.env.INTERNAL_API_KEY;

  if (!internalApiKey) {
    throw new Error("INTERNAL_API_KEY não configurada no Next.js");
  }

  const headers: Record<string, string> = {
    "X-Internal-API-Key": internalApiKey,
    "X-User-Id": userId,
  };

  if (includeJsonContentType) {
    headers["Content-Type"] = "application/json";
  }

  return headers;
}
