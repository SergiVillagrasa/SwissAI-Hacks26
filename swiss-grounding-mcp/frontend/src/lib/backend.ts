export const MAX_CHAT_MESSAGE_LENGTH = 8000;

export function backendHeaders(
  extra: Record<string, string> = {}
): Record<string, string> {
  const apiKey = import.meta.env.VITE_AGENT_BACKEND_API_KEY;
  return {
    ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}),
    ...extra,
  };
}

export class BackendError extends Error {
  readonly status: number;

  constructor(status: number) {
    super(`Backend request failed with status ${status}`);
    this.name = "BackendError";
    this.status = status;
  }
}
