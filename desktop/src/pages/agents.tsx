import { LoadingOverlay } from "@/components/ui/loading-overlay";
import { useEffect, useState } from "react";
import { Bot, Mic, Plug, Plus, Square, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useAgentChat } from "@/hooks/use-agent-chat";
import { useRecorder } from "@/hooks/use-recorder";
import { useEngineSelection, useLibrary } from "@/hooks/use-studio";
import { api } from "@/lib/api";
import { AGENT_ICONS } from "@/lib/agent-icons";
import { useEngineStatus } from "@/lib/engine-status";
import { PAGE_DESCRIPTIONS, PAGE_TITLES } from "@/lib/pages";
import type { AgentProfile, McpServerDraft, ModelInfo, SynthesisParams } from "@/lib/types";

const DEFAULT_PROMPT = "You are a friendly, concise voice assistant.";

const PHASE_LABELS = {
  idle: "",
  listening: "Listening",
  thinking: "Thinking",
  speaking: "Speaking",
} as const;

function describeError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function Avatar({ icon }: { icon: string }) {
  const Icon = AGENT_ICONS[icon] ?? AGENT_ICONS.bot;
  return (
    <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
      <Icon className="size-4" />
    </span>
  );
}

function Conversation({ agent, engineName, params }: { agent: AgentProfile; engineName: string; params: SynthesisParams }) {
  const chat = useAgentChat(agent, engineName, params);
  const recorder = useRecorder((wav) => void chat.hear(wav));
  const busy = chat.phase === "thinking";

  const toggleListening = async () => {
    if (recorder.recording) {
      recorder.stop();
      return;
    }
    chat.prepare();
    try {
      await recorder.start();
      chat.setPhase("listening");
    } catch (error) {
      toast.error("Microphone unavailable", { description: describeError(error) });
    }
  };

  return (
    <div className="flex h-full min-h-[28rem] flex-col rounded-lg border bg-card">
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <Avatar icon={agent.icon} />
          <div>
            <h2 className="text-sm font-medium">{agent.name}</h2>
            {agent.mcp_servers.length > 0 && (
              <p className="flex items-center gap-1 text-xs text-muted-foreground">
                <Plug className="size-3" />
                {agent.mcp_servers.map((server) => server.name).join(", ")}
              </p>
            )}
          </div>
        </div>
        <span className="text-xs text-muted-foreground" aria-live="polite">
          {PHASE_LABELS[chat.phase]}
        </span>
      </div>
      <ol className="flex flex-1 flex-col gap-2 overflow-y-auto p-4 text-sm">
        {chat.turns.length === 0 && (
          <li className="m-auto text-muted-foreground">Press Talk and speak to {agent.name}.</li>
        )}
        {chat.turns.map((turn, index) => (
          <li
            key={index}
            className={
              turn.role === "user"
                ? "max-w-[80%] self-end rounded-lg bg-primary px-3 py-2 text-primary-foreground"
                : "max-w-[80%] self-start rounded-lg bg-muted px-3 py-2"
            }
          >
            {turn.content}
          </li>
        ))}
      </ol>
      <div className="flex justify-center border-t p-4">
        <Button
          onClick={toggleListening}
          disabled={busy}
          variant={recorder.recording ? "outline" : "default"}
        >
          {recorder.recording ? <Square className="size-4" /> : <Mic className="size-4" />}
          {recorder.recording ? "Stop and send" : "Talk"}
        </Button>
      </div>
    </div>
  );
}

export function AgentsPage() {
  const { status } = useEngineStatus();
  const online = status !== "offline";
  const { voices, engines } = useLibrary(online);
  const { activeEngine, params } = useEngineSelection(engines);

  const [agents, setAgents] = useState<AgentProfile[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [voiceId, setVoiceId] = useState<number | null>(null);
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [creating, setCreating] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [icon, setIcon] = useState("bot");
  const [llmModels, setLlmModels] = useState<ModelInfo[]>([]);
  const [llmModel, setLlmModel] = useState("agent-llm");
  const [servers, setServers] = useState<McpServerDraft[]>([]);
  const [draft, setDraft] = useState<McpServerDraft>({ name: "", url: "", token: "" });
  const [checking, setChecking] = useState(false);

  const agent = agents.find((item) => item.id === selectedId) ?? agents[0] ?? null;
  useEffect(() => {
    if (!online) return;
    void api.warmAgents().catch(() => undefined);
    api
      .listModels()
      .then((models) =>
        {
          const installed = models.filter((model) => model.id.startsWith("agent-llm") && model.is_downloaded);
          setLlmModels(installed);
          setLlmModel((current) => installed.some((model) => model.id === current) ? current : (installed[0]?.id ?? current));
        },
      )
      .catch(() => setLlmModels([]));
    api.listAgents().then(setAgents).catch(() => setAgents([])).finally(() => setLoaded(true));
  }, [online]);

  const create = async () => {
    try {
      const created = await api.createAgent({ name: name.trim(), voice_id: voiceId, system_prompt: prompt.trim(), icon, llm_model: llmModel, mcp_servers: servers });
      setAgents((previous) => [created, ...previous]);
      setSelectedId(created.id);
      setName("");
      setIcon("bot");
      setServers([]);
      setCreating(false);
    } catch (error) {
      toast.error("Could not create the agent", { description: describeError(error) });
    }
  };

  const addServer = async () => {
    setChecking(true);
    try {
      const tools = await api.testMcpServer(draft.url.trim(), draft.token);
      setServers((previous) => [...previous, { ...draft, name: draft.name.trim(), url: draft.url.trim() }]);
      setDraft({ name: "", url: "", token: "" });
      toast.success(`Connected: ${tools.length} tool${tools.length === 1 ? "" : "s"} found`);
    } catch (error) {
      toast.error("Could not connect to that MCP server", { description: describeError(error) });
    } finally {
      setChecking(false);
    }
  };

  const remove = async (target: AgentProfile) => {
    try {
      await api.deleteAgent(target.id);
      setAgents((previous) => previous.filter((item) => item.id !== target.id));
    } catch (error) {
      toast.error("Could not delete the agent", { description: describeError(error) });
    }
  };

  return (
    <div className="space-y-6">
      <LoadingOverlay show={!loaded && online} />
      <PageHeader title={PAGE_TITLES.agents} description={PAGE_DESCRIPTIONS.agents} />
      {loaded && agents.length === 0 ? (
        <div className="flex min-h-96 flex-col items-center justify-center gap-4 rounded-lg border border-dashed text-center">
          <span className="flex size-12 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Bot className="size-6" />
          </span>
          <p className="text-sm text-muted-foreground">Create an agent to start talking.</p>
          <Button onClick={() => setCreating(true)}>
            <Plus className="size-4" /> Create agent
          </Button>
        </div>
      ) : (
      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        <section className="space-y-3">
          <Button variant="outline" size="sm" onClick={() => setCreating(true)}>
            <Plus className="size-4" /> New agent
          </Button>
          <ul className="space-y-2">
            {agents.map((item) => (
              <li
                key={item.id}
                className={`flex items-center gap-2 rounded-lg border p-2 ${item.id === agent?.id ? "border-primary bg-primary/5" : "bg-card"}`}
              >
                <button
                  type="button"
                  className="flex min-w-0 flex-1 items-center gap-2 text-left text-sm"
                  onClick={() => setSelectedId(item.id)}
                >
                  <Avatar icon={item.icon} />
                  <span className="min-w-0">
                    <span className="block truncate font-medium">{item.name}</span>
                    {item.mcp_servers.length > 0 && (
                      <Badge variant="secondary" className="mt-0.5">
                        {item.mcp_servers.length} MCP
                      </Badge>
                    )}
                  </span>
                </button>
                <Button variant="ghost" size="icon" aria-label={`Delete ${item.name}`} onClick={() => remove(item)}>
                  <Trash2 className="size-4" />
                </Button>
              </li>
            ))}
          </ul>
        </section>

        <section className="space-y-4">
          {agent ? (
            <Conversation key={agent.id} agent={agent} engineName={activeEngine?.name ?? "Chatterbox TTS"} params={params} />
          ) : (
            <div className="flex min-h-72 items-center justify-center rounded-lg border border-dashed text-sm text-muted-foreground">Create an agent to start talking.</div>
          )}
        </section>
      </div>
      )}

      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>New agent</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <Field>
              <FieldLabel htmlFor="agent-name">Name</FieldLabel>
              <Input id="agent-name" value={name} onChange={(event) => setName(event.target.value)} />
            </Field>
            <Field>
              <FieldLabel>Icon</FieldLabel>
              <div className="flex flex-wrap gap-1.5">
                {Object.keys(AGENT_ICONS).map((key) => {
                  const Icon = AGENT_ICONS[key];
                  return (
                    <button
                      key={key}
                      type="button"
                      aria-label={key}
                      aria-pressed={icon === key}
                      onClick={() => setIcon(key)}
                      className={`flex size-9 items-center justify-center rounded-md border ${icon === key ? "border-primary bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground"}`}
                    >
                      <Icon className="size-4" />
                    </button>
                  );
                })}
              </div>
            </Field>
            <Field>
              <FieldLabel htmlFor="agent-voice">Voice</FieldLabel>
              <Select
                value={voiceId === null ? "none" : String(voiceId)}
                onValueChange={(value) => setVoiceId(value && value !== "none" ? Number(value) : null)}
              >
                <SelectTrigger id="agent-voice" className="w-full">
                  <SelectValue>
                    {(value) =>
                      value === "none" || value == null
                        ? "Text only"
                        : (voices.find((voice) => String(voice.id) === value)?.name ?? "Text only")
                    }
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Text only</SelectItem>
                  {voices.map((voice) => (
                    <SelectItem key={voice.id} value={String(voice.id)}>
                      {voice.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            {llmModels.length > 1 ? (
              <Field>
                <FieldLabel htmlFor="agent-llm">Language model</FieldLabel>
                <Select value={llmModel} onValueChange={(value) => value && setLlmModel(value)}>
                  <SelectTrigger id="agent-llm" className="w-full">
                    <SelectValue>
                      {(value) => llmModels.find((model) => model.id === value)?.name ?? "Qwen3 4B Instruct"}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {llmModels.map((model) => (
                      <SelectItem key={model.id} value={model.id}>
                        {model.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
            ) : null}
            <Field>
              <FieldLabel htmlFor="agent-prompt">Instructions</FieldLabel>
              <Textarea id="agent-prompt" rows={4} value={prompt} onChange={(event) => setPrompt(event.target.value)} />
            </Field>
            <div className="space-y-2">
              <p className="text-sm font-medium">MCP servers</p>
              <p className="text-xs text-muted-foreground">
                Remote servers over http(s) only. The agent can call their tools while it talks.
              </p>
              {servers.map((server) => (
                <div key={server.url} className="flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm">
                  <span className="min-w-0 truncate">
                    {server.name} <span className="text-xs text-muted-foreground">{server.url}</span>
                  </span>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label={`Remove ${server.name}`}
                    onClick={() => setServers((previous) => previous.filter((item) => item !== server))}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              ))}
              <div className="grid gap-2 sm:grid-cols-2">
                <Input
                  aria-label="Server name"
                  placeholder="Name"
                  value={draft.name}
                  onChange={(event) => setDraft({ ...draft, name: event.target.value })}
                />
                <Input
                  aria-label="Access token"
                  type="password"
                  placeholder="Token (optional)"
                  value={draft.token}
                  onChange={(event) => setDraft({ ...draft, token: event.target.value })}
                />
                <Input
                  aria-label="Server URL"
                  className="sm:col-span-2"
                  placeholder="https://example.com/mcp"
                  value={draft.url}
                  onChange={(event) => setDraft({ ...draft, url: event.target.value })}
                />
              </div>
              <Button
                variant="outline"
                size="sm"
                disabled={!draft.name.trim() || !draft.url.trim() || checking}
                onClick={() => void addServer()}
              >
                {checking ? "Connecting…" : "Test and add"}
              </Button>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreating(false)}>
              Cancel
            </Button>
            <Button onClick={create} disabled={!name.trim() || !prompt.trim()}>
              Create agent
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
