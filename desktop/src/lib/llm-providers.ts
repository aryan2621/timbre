export type LlmProvider = "local" | "ollama";

export const PROVIDER_LABELS: Record<LlmProvider, string> = {
  local: "Built in",
  ollama: "Ollama",
};
