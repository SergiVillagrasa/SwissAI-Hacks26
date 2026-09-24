export async function transcribeAudio(backendUrl: string, audio: Blob): Promise<string> {
  const formData = new FormData();
  formData.append("audio", audio, "utterance.webm");

  const response = await fetch(`${backendUrl}/api/voice/transcribe`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Voice backend responded with ${response.status}`);
  }

  const data = (await response.json()) as { text: string };
  return data.text;
}

export async function synthesizeSpeech(backendUrl: string, text: string): Promise<Blob> {
  const response = await fetch(`${backendUrl}/api/voice/speak`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });

  if (!response.ok) {
    throw new Error(`Voice backend responded with ${response.status}`);
  }

  return await response.blob();
}
