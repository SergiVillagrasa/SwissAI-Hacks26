import { BackendError, backendHeaders } from "./backend";

export async function transcribeAudio(backendUrl: string, audio: Blob): Promise<string> {
  const formData = new FormData();
  formData.append("audio", audio, "utterance.webm");

  const response = await fetch(`${backendUrl}/api/voice/transcribe`, {
    method: "POST",
    headers: backendHeaders(),
    body: formData,
  });

  if (!response.ok) {
    throw new BackendError(response.status);
  }

  const data = (await response.json()) as { text: string };
  return data.text;
}

export async function synthesizeSpeech(backendUrl: string, text: string): Promise<Blob> {
  const response = await fetch(`${backendUrl}/api/voice/speak`, {
    method: "POST",
    headers: backendHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ text: text.slice(0, 1500) }),
  });

  if (!response.ok) {
    throw new BackendError(response.status);
  }

  return await response.blob();
}
