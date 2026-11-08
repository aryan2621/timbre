import { CircleHelp } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { HuggingFaceStatus } from "@/lib/types";

const TOKENS_URL = "https://huggingface.co/settings/tokens";

function CopyLink({ url }: { url: string }) {
  return (
    <span className="mt-1 flex items-center gap-2">
      <code className="min-w-0 flex-1 select-all truncate rounded bg-muted px-2 py-1 text-xs">{url}</code>
      <Button
        variant="outline"
        size="xs"
        onClick={() => void navigator.clipboard.writeText(url).then(() => toast.success("Link copied"))}
      >
        Copy
      </Button>
    </span>
  );
}

function TokenSteps({ gatedUrls }: { gatedUrls: string[] }) {
  return (
    <ol className="list-decimal space-y-4 pl-5 text-sm">
      <li>
        Sign in to Hugging Face, or create a free account.
        <CopyLink url="https://huggingface.co/join" />
      </li>
      <li>
        Accept the licence on each gated model page you want.
        {gatedUrls.map((url) => (
          <CopyLink key={url} url={url} />
        ))}
      </li>
      <li>
        Open your access tokens page and choose <strong>Create new token</strong>.
        <CopyLink url={TOKENS_URL} />
      </li>
      <li>
        Pick the <strong>Read</strong> type, name it, and create it. Copy the token that starts with{" "}
        <code>hf_</code>. It is shown only once.
      </li>
      <li>Paste it into the box on this page and press <strong>Save token</strong>.</li>
    </ol>
  );
}

interface HuggingFaceTokenProps {
  gatedUrls?: string[];
  status: HuggingFaceStatus | null;
  onChange: (status: HuggingFaceStatus) => void;
}

function describe(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function HuggingFaceToken({ status, onChange, gatedUrls = [] }: HuggingFaceTokenProps) {
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);

  const run = async (action: () => Promise<HuggingFaceStatus>, success: string) => {
    setBusy(true);
    try {
      onChange(await action());
      setToken("");
      toast.success(success);
    } catch (error) {
      toast.error("Hugging Face token", { description: describe(error) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <Field className="gap-1.5">
        <div className="flex items-center gap-2">
          <FieldLabel htmlFor="hf-token">Your Hugging Face token</FieldLabel>
          <Button
            variant="ghost"
            size="icon-xs"
            aria-label="How do I get a token?"
            title="How do I get a token?"
            onClick={() => setHelpOpen(true)}
          >
            <CircleHelp />
          </Button>
        </div>
        {status?.configured ? (
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <span>
              {status.username ? `Signed in as ${status.username}` : "A token is saved"}
              {status.valid === false ? " (no longer valid, replace it)" : ""}
              {status.reachable === false ? " (could not reach Hugging Face to check it)" : ""}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={busy}
              onClick={() => void run(api.removeHuggingFaceToken, "Token removed")}
            >
              Remove token
            </Button>
          </div>
        ) : (
          <form
            className="flex flex-wrap gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              void run(() => api.saveHuggingFaceToken(token.trim()), "Token saved");
            }}
          >
            <Input
              id="hf-token"
              className="h-8 min-w-0 flex-1"
              type="password"
              autoComplete="off"
              spellCheck={false}
              value={token}
              placeholder="hf_..."
              onChange={(event) => setToken(event.target.value)}
            />
            <Button type="submit" disabled={busy || token.trim().length === 0}>
              Save token
            </Button>
          </form>
        )}
      </Field>
      <Dialog open={helpOpen} onOpenChange={setHelpOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Get a Hugging Face token</DialogTitle>
          </DialogHeader>
          <TokenSteps gatedUrls={gatedUrls} />
        </DialogContent>
      </Dialog>
    </div>
  );
}
