import { toast } from "sonner";
import { IS_TAURI, downloadBlob, pickSavePath, writeBlobToPath } from "@/lib/desktop";

export async function exportAudio(url: string, filePrefix: string): Promise<void> {
  try {
    const response = await fetch(url);
    const blob = await response.blob();
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
    const filename = `${filePrefix}-${stamp}.wav`;

    if (IS_TAURI) {
      const path = await pickSavePath(filename, "wav");
      if (!path) return;
      if (await writeBlobToPath(path, blob)) {
        toast.success("Export saved", { description: path });
        return;
      }
    }
    downloadBlob(blob, filename);
    toast.success("Export started", { description: filename });
  } catch {
    toast.error("Export failed");
  }
}
