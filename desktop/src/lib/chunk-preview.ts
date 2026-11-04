/**
 * A client-side mirror of the backend chunker.
 *
 * The Studio shows how the script will be split into sentences *before* the
 * render starts. It uses the same rules as `app/audio/chunker.py` so the
 * preview always matches what the engine will actually render.
 */

const ABBREVIATIONS = new Set([
  "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "vs", "etc", "fig", "e.g", "i.e",
  "inc", "ltd", "co", "corp", "u.s", "u.k", "jan", "feb", "mar", "apr", "aug",
  "sept", "oct", "nov", "dec",
]);

export function splitIntoSentences(text: string): string[] {
  const cleaned = text.trim();
  if (!cleaned) return [];

  const paragraphs = cleaned.split(/\n+/).map((part) => part.trim()).filter(Boolean);
  const sentences: string[] = [];

  for (const paragraph of paragraphs) {
    const raw = paragraph.split(/(?<=[.!?])\s+(?=[A-Z0-9"'‘“])/);
    let buffer = "";

    for (const part of raw) {
      if (!part) continue;
      if (buffer) {
        const words = buffer.replace(/[.!?]+$/, "").trim().split(/\s+/);
        const lastWord = (words[words.length - 1] ?? "").toLowerCase();
        if (ABBREVIATIONS.has(lastWord)) {
          buffer += ` ${part}`;
          continue;
        }
        sentences.push(buffer.trim());
        buffer = part;
      } else {
        buffer = part;
      }
    }

    if (buffer) sentences.push(buffer.trim());
  }

  return sentences;
}

export function chunkText(
  text: string,
  maxCharsPerChunk = 110,
): string[] {
  const sentences = splitIntoSentences(text);
  if (!sentences.length) return [];

  const chunks: string[] = [];
  let current = "";

  for (const sentence of sentences) {
    if (sentence.length > maxCharsPerChunk) {
      if (current) {
        chunks.push(current.trim());
        current = "";
      }
      // Long sentences are split on secondary punctuation, then on words.
      const parts = sentence.split(/([,;:—–-])/);
      let buffer = "";
      for (const part of parts) {
        if (buffer.length + part.length <= maxCharsPerChunk) {
          buffer += part;
        } else {
          if (buffer.trim()) chunks.push(buffer.trim());
          if (part.length > maxCharsPerChunk) {
            const words = part.split(" ");
            let wordBuffer = "";
            for (const word of words) {
              if (wordBuffer.length + word.length + 1 <= maxCharsPerChunk) {
                wordBuffer = `${wordBuffer} ${word}`.trim();
              } else {
                if (wordBuffer) chunks.push(wordBuffer);
                wordBuffer = word;
              }
            }
            buffer = wordBuffer;
          } else {
            buffer = part;
          }
        }
      }
      if (buffer.trim()) chunks.push(buffer.trim());
      continue;
    }

    if (current && current.length + sentence.length + 1 > maxCharsPerChunk) {
      chunks.push(current.trim());
      current = sentence;
    } else {
      current = current ? `${current} ${sentence}` : sentence;
    }
  }

  if (current) chunks.push(current.trim());
  return chunks;
}

export function countWords(text: string): number {
  const trimmed = text.trim();
  return trimmed ? trimmed.split(/\s+/).length : 0;
}
