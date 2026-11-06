import { useCallback, useEffect, useRef, useState } from "react";

/** Voice cloning needs 5-30s; stop automatically at the top of that range. */
export const MAX_RECORD_SECONDS = 30;

/** Mono 16-bit WAV, the format the API reads without extra codecs. */
function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const view = new DataView(new ArrayBuffer(44 + samples.length * 2));
  const text = (offset: number, value: string) =>
    [...value].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)));
  text(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  text(8, "WAVEfmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  text(36, "data");
  view.setUint32(40, samples.length * 2, true);
  samples.forEach((sample, i) => {
    const clamped = Math.max(-1, Math.min(1, sample));
    view.setInt16(44 + i * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
  });
  return new Blob([view], { type: "audio/wav" });
}

/** Records the microphone and resolves with a WAV blob when stopped. */
export function useRecorder(onDone: (wav: Blob, seconds: number) => void) {
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const recorder = useRef<MediaRecorder | null>(null);
  const timer = useRef<number>(0);
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  const stop = useCallback(() => {
    window.clearInterval(timer.current);
    if (recorder.current?.state === "recording") recorder.current.stop();
  }, []);

  const start = useCallback(async () => {
    // Throws NotAllowedError / NotFoundError; the caller shows the toast.
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const media = new MediaRecorder(stream);
    const chunks: Blob[] = [];
    media.ondataavailable = (event) => chunks.push(event.data);
    media.onstop = async () => {
      stream.getTracks().forEach((track) => track.stop());
      setRecording(false);
      const context = new AudioContext();
      try {
        const decoded = await context.decodeAudioData(await new Blob(chunks).arrayBuffer());
        onDoneRef.current(encodeWav(decoded.getChannelData(0), decoded.sampleRate), decoded.duration);
      } finally {
        void context.close();
      }
    };
    recorder.current = media;
    media.start();
    setSeconds(0);
    setRecording(true);
    const startedAt = Date.now();
    timer.current = window.setInterval(() => {
      const elapsed = (Date.now() - startedAt) / 1000;
      setSeconds(elapsed);
      if (elapsed >= MAX_RECORD_SECONDS) stop();
    }, 200);
  }, [stop]);

  useEffect(() => () => {
    window.clearInterval(timer.current);
    if (recorder.current?.state === "recording") {
      recorder.current.onstop = null;
      recorder.current.stop();
      recorder.current.stream.getTracks().forEach((track) => track.stop());
    }
  }, []);

  return { recording, seconds, start, stop };
}
