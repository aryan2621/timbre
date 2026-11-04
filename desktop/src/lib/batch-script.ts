/**
 * Batch script parsing.
 *
 * The Batch screen used to parse the file inside the component. It lives here
 * now so the importer, the preview and the tests all agree on the format.
 */

export interface ParsedLine {
  index: number;
  text: string;
  filename: string;
}

function pad(index: number): string {
  return String(index).padStart(4, "0");
}

function parseCsv(content: string): ParsedLine[] {
  const rows = content
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  // The first row is treated as a header when it has no obvious script text.
  const body = rows.length > 1 && !/[.!?]/.test(rows[0]) ? rows.slice(1) : rows;

  return body
    .map((row, index) => {
      const [text = "", custom = ""] = row.split(",");
      return {
        index: index + 1,
        text: text.trim(),
        filename: custom.trim() || `batch_${pad(index + 1)}.wav`,
      };
    })
    .filter((item) => item.text.length > 0);
}

function parseSrt(content: string): ParsedLine[] {
  return content
    .split(/\r?\n\s*\r?\n/)
    .map((block) =>
      block
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter((line) => line && !/^\d+$/.test(line) && !line.includes("-->"))
        .join(" "),
    )
    .filter(Boolean)
    .map((text, index) => ({
      index: index + 1,
      text,
      filename: `subtitle_${pad(index + 1)}.wav`,
    }));
}

function parsePlainText(content: string): ParsedLine[] {
  return content
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((text, index) => ({
      index: index + 1,
      text,
      filename: `line_${pad(index + 1)}.wav`,
    }));
}

/** Parses a `.txt`, `.csv`, `.srt` or `.md` script into renderable lines. */
export function parseScript(name: string, content: string): ParsedLine[] {
  const extension = name.split(".").pop()?.toLowerCase() ?? "";
  if (extension === "csv") return parseCsv(content);
  if (extension === "srt") return parseSrt(content);
  return parsePlainText(content);
}
