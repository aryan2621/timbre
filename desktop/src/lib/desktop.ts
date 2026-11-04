/**
 * Desktop integration helpers.
 *
 * The old app asked the user to type an absolute file path ("/Users/me/voice_sample.wav")
 * and had a fake read-only "Output folder" field. These helpers use the native
 * Tauri pickers when the app runs in the desktop shell and degrade to the
 * browser file APIs in a plain web session.
 */

export const IS_TAURI =
  typeof window !== "undefined" &&
  ("__TAURI_INTERNALS__" in window || "__TAURI__" in window);

async function pickFile(options: {
  title: string;
  extensions: string[];
  multiple?: boolean;
}): Promise<string | null> {
  if (!IS_TAURI) return null;
  try {
    const { open } = await import("@tauri-apps/plugin-dialog");
    const selected = (await open({
      title: options.title,
      multiple: options.multiple ?? false,
      filters: [{ name: options.title, extensions: options.extensions }],
    })) as string | string[] | null;
    if (typeof selected === "string") return selected;
    if (Array.isArray(selected) && selected.length > 0) return selected[0] ?? null;
  } catch (error) {
    console.error("File picker failed", error);
  }
  return null;
}

/** Opens a native picker for a reference recording. */
export function pickAudioFile(): Promise<string | null> {
  return pickFile({
    title: "Reference recording",
    extensions: ["wav", "flac", "ogg", "mp3", "m4a", "aac", "aiff"],
  });
}

/** Opens a native picker for a batch script. */
export function pickScriptFile(): Promise<string | null> {
  return pickFile({
    title: "Batch script",
    extensions: ["txt", "csv", "srt", "md"],
  });
}

/** Opens a native picker for the export folder. */
export async function pickFolder(title = "Output folder"): Promise<string | null> {
  if (!IS_TAURI) return null;
  try {
    const { open } = await import("@tauri-apps/plugin-dialog");
    const selected = await open({ title, directory: true });
    return typeof selected === "string" ? selected : null;
  } catch (error) {
    console.error("Folder picker failed", error);
    return null;
  }
}

/** Opens the native save dialog and returns the chosen path. */
export async function pickSavePath(
  defaultName: string,
  extension = "wav",
): Promise<string | null> {
  if (!IS_TAURI) return null;
  try {
    const { save } = await import("@tauri-apps/plugin-dialog");
    return await save({
      title: "Export render",
      defaultPath: defaultName,
      filters: [{ name: extension.toUpperCase(), extensions: [extension] }],
    });
  } catch (error) {
    console.error("Save dialog failed", error);
    return null;
  }
}

/** Writes a blob to a path chosen in the native save dialog. */
export async function writeBlobToPath(path: string, blob: Blob): Promise<boolean> {
  if (!IS_TAURI) return false;
  try {
    const { writeFile } = await import("@tauri-apps/plugin-fs");
    const bytes = new Uint8Array(await blob.arrayBuffer());
    await writeFile(path, bytes);
    return true;
  } catch (error) {
    console.error("Could not write the file", error);
    return false;
  }
}

/** Reads a text file (batch scripts) from a native path. */
export async function readTextFile(path: string): Promise<string | null> {
  if (!IS_TAURI) return null;
  try {
    const { readTextFile } = await import("@tauri-apps/plugin-fs");
    return await readTextFile(path);
  } catch (error) {
    console.error("Could not read the file", error);
    return null;
  }
}

/** The browser fallback: downloads a blob through a temporary anchor. */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Reads a file that the user dropped or picked with a browser input. */
export function readFileAsText(file: File): Promise<string> {
  return file.text();
}
