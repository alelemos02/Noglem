/**
 * URL base do backend FastAPI.
 * Em desenvolvimento: http://localhost:8000
 * Em produção: URL do Railway
 */
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getBackendUrl(path: string): string {
  return `${API_URL}${path}`;
}
