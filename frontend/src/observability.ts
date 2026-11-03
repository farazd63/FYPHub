export type WorkflowFailureCategory = "NETWORK_ERROR" | "AUTHENTICATION_ERROR" | "AUTHORIZATION_ERROR" | "NOT_FOUND" | "VALIDATION_ERROR" | "SERVER_ERROR" | "AI_PROVIDER_ERROR" | "AI_VALIDATION_ERROR" | "DETERMINISTIC_FALLBACK";

export type ObservabilityResponse = { response: Response; requestId: string | null; durationMs: number };

const development = import.meta.env.DEV;

export const classifyHttpStatus = (status: number): WorkflowFailureCategory => status === 401 ? "AUTHENTICATION_ERROR" : status === 403 ? "AUTHORIZATION_ERROR" : status === 404 ? "NOT_FOUND" : status === 422 ? "VALIDATION_ERROR" : status >= 500 ? "SERVER_ERROR" : "SERVER_ERROR";

export async function observeFetch(workflow: string, url: string, init: RequestInit = {}): Promise<ObservabilityResponse> {
  const started = performance.now();
  if (development) console.debug(JSON.stringify({ event: `${workflow}.start`, endpoint: new URL(url).pathname }));
  try {
    const response = await fetch(url, init);
    const result = { response, requestId: response.headers.get("X-Request-ID"), durationMs: Math.round((performance.now() - started) * 100) / 100 };
    if (development) console.debug(JSON.stringify({ event: response.ok ? `${workflow}.success` : `${workflow}.failure`, endpoint: new URL(url).pathname, status: response.status, request_id: result.requestId, duration_ms: result.durationMs, category: response.ok ? undefined : classifyHttpStatus(response.status) }));
    return result;
  } catch (error) {
    if (development) console.debug(JSON.stringify({ event: `${workflow}.failure`, endpoint: new URL(url).pathname, status: 0, duration_ms: Math.round((performance.now() - started) * 100) / 100, category: "NETWORK_ERROR", error_type: error instanceof Error ? error.name : "UnknownError" }));
    throw error;
  }
}
