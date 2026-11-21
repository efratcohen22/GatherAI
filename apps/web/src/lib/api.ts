const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public status: number, message: string, public requestId?: string) {
    super(message);
  }
}

let tokenProvider: () => Promise<string | null> = async () => null;
let onUnauthorized: () => void = () => {};

export function configureApi(getToken: () => Promise<string | null>, unauthorized: () => void) {
  tokenProvider = getToken;
  onUnauthorized = unauthorized;
}

export const hasToken = async () => !!(await tokenProvider());

async function raw(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await tokenProvider();
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: {
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
  } catch {
    throw new ApiError(0, "We couldn't reach the server. Check your connection and try again.");
  }
  if (!response.ok) {
    if (response.status === 401 && token) onUnauthorized();
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    const requestId = response.headers.get("X-Request-ID") ?? undefined;
    let message = typeof detail === "string" ? detail : Array.isArray(detail) ? "Please check the highlighted information." : "Something went wrong.";
    if (response.status >= 500 && requestId) message += ` (Reference: ${requestId.slice(0, 8)})`;
    throw new ApiError(response.status, message, requestId);
  }
  return response;
}

export async function api<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const response = await raw(path, { method, body: body === undefined ? undefined : JSON.stringify(body) });
  return (response.status === 204 ? undefined : await response.json()) as T;
}

export async function downloadFile(path: string, filename: string) {
  const blob = await (await raw(path)).blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
