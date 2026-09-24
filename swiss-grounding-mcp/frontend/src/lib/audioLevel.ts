export type LevelListener = (level: number) => void;

function runMeter(analyser: AnalyserNode, onLevel: LevelListener): () => void {
  const data = new Float32Array(analyser.fftSize);
  let raf = 0;
  let stopped = false;

  function tick() {
    if (stopped) return;
    analyser.getFloatTimeDomainData(data);
    let sum = 0;
    for (let i = 0; i < data.length; i += 1) sum += data[i] * data[i];
    const rms = Math.sqrt(sum / data.length);
    // Mic/TTS RMS sits well under 1.0 in practice; scale up so quiet
    // speech still reads as visible motion, and clamp the loud end.
    onLevel(Math.min(1, rms * 4.5));
    raf = requestAnimationFrame(tick);
  }
  raf = requestAnimationFrame(tick);

  return () => {
    stopped = true;
    cancelAnimationFrame(raf);
  };
}

/** Reports the live input level of a microphone stream. Analysis-only: never routed to speakers. */
export function meterFromStream(stream: MediaStream, onLevel: LevelListener): () => void {
  const ctx = new AudioContext();
  const source = ctx.createMediaStreamSource(stream);
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 256;
  source.connect(analyser);

  const stopTicking = runMeter(analyser, onLevel);
  return () => {
    stopTicking();
    source.disconnect();
    void ctx.close();
  };
}

/** Reports the live playback level of an <audio> element, without muting it. */
export function meterFromAudioElement(element: HTMLAudioElement, onLevel: LevelListener): () => void {
  const ctx = new AudioContext();
  const source = ctx.createMediaElementSource(element);
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 256;
  // Route audio -> analyser -> speakers so metering never silences playback.
  source.connect(analyser);
  analyser.connect(ctx.destination);

  const stopTicking = runMeter(analyser, onLevel);
  return () => {
    stopTicking();
    source.disconnect();
    analyser.disconnect();
    void ctx.close();
  };
}
