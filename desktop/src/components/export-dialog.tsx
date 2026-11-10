import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { SoundBars } from "@/components/ui/sound-bars";
import { closeExport, sanitizeFilename, saveAudio, useExportRequest } from "@/lib/export-audio";

export function ExportDialog() {
  const request = useExportRequest();
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (request) setName(request.name);
  }, [request]);

  const valid = sanitizeFilename(name).length > 0;

  const save = async () => {
    if (!request || !valid || saving) return;
    setSaving(true);
    const saved = await saveAudio(request.url, name);
    setSaving(false);
    if (saved) closeExport();
  };

  return (
    <Dialog open={request !== null} onOpenChange={(open) => !open && !saving && closeExport()}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Export audio</DialogTitle>
          <DialogDescription>Name the file. It is saved as a WAV in your Downloads folder.</DialogDescription>
        </DialogHeader>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
        >
          <Field>
            <FieldLabel htmlFor="export-name">File name</FieldLabel>
            <div className="flex items-center gap-2">
              <Input
                id="export-name"
                value={name}
                autoFocus
                onFocus={(event) => event.currentTarget.select()}
                onChange={(event) => setName(event.target.value)}
              />
              <span className="text-sm text-muted-foreground">.wav</span>
            </div>
          </Field>
          <DialogFooter className="mt-4">
            <Button type="button" variant="outline" onClick={closeExport} disabled={saving}>
              Cancel
            </Button>
            <Button type="submit" disabled={!valid || saving}>
              {saving ? <SoundBars className="h-3.5 text-current" /> : null}
              Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
