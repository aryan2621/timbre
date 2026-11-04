/**
 * Audio decoding and waveform peak extraction utilities.
 */

/**
 * Decodes an audio file from a URL and extracts normalized peak amplitudes.
 * Uses Web Audio API to analyze true audio buffer PCM channel data.
 */
export async function extractAudioPeaks(url: string, count = 220): Promise<number[]> {
  try {
    const response = await fetch(url);
    if (!response.ok) return [];
    const arrayBuffer = await response.arrayBuffer();

    const AudioCtx =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) return [];

    const ctx = new AudioCtx();
    const audioBuffer = await ctx.decodeAudioData(arrayBuffer);
    const channelData = audioBuffer.getChannelData(0);
    const totalSamples = channelData.length;

    if (totalSamples === 0) {
      await ctx.close().catch(() => {});
      return [];
    }

    const step = Math.max(1, Math.floor(totalSamples / count));
    const peaks: number[] = [];
    let globalMax = 0;

    for (let i = 0; i < count; i++) {
      const start = i * step;
      const end = Math.min(start + step, totalSamples);
      let localMax = 0;
      for (let j = start; j < end; j++) {
        const val = Math.abs(channelData[j] ?? 0);
        if (val > localMax) localMax = val;
      }
      peaks.push(localMax);
      if (localMax > globalMax) globalMax = localMax;
    }

    await ctx.close().catch(() => {});

    if (globalMax <= 1e-6) {
      return peaks.map(() => 0.04);
    }

    return peaks.map((p) =>
      Math.max(0.04, Math.round((p / globalMax) * 1000) / 1000),
    );
  } catch (err) {
    console.warn("Could not extract real audio peaks:", err);
    return [];
  }
}

