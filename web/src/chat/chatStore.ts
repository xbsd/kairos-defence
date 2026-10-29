// The optional chat (SPEC §18.3, D-162): hidden unless GET /api/chat/status says a provider is
// configured (`llm.provider: none` is the default). Replies come from the server's tool loop over
// the §18.1 tools; this store only keeps the conversation and never writes anything itself.
import { createStore } from "zustand/vanilla";

import { api } from "../api/client";
import type { ChatMessage, ChatStatus, ChatToolCall } from "../api/messages";

export interface ChatTurn extends ChatMessage {
  tools?: ChatToolCall[];
}

export interface ChatState {
  status: ChatStatus | null;
  open: boolean;
  turns: ChatTurn[];
  busy: boolean;
  error: string | null;
}

export const chatStore = createStore<ChatState>()(() => ({
  status: null,
  open: false,
  turns: [],
  busy: false,
  error: null,
}));

/** Ask the server once whether chat is on; any failure (no route, 409, offline) means off. */
export async function loadChatStatus(): Promise<void> {
  try {
    const status = await api.chatStatus();
    chatStore.setState({ status });
  } catch {
    chatStore.setState({ status: { enabled: false, provider: "none", model: "", tools: [] } });
  }
}

export function setChatOpen(open: boolean): void {
  chatStore.setState({ open });
}

/** Send one question with the conversation so far; the reply arrives with its tool calls. */
export async function sendChat(text: string): Promise<void> {
  const q = text.trim();
  const st = chatStore.getState();
  if (!q || st.busy || !st.status?.enabled) return;
  const turns: ChatTurn[] = [...st.turns, { role: "user", content: q }];
  chatStore.setState({ turns, busy: true, error: null });
  try {
    const r = await api.chat(turns.map(({ role, content }) => ({ role, content })));
    chatStore.setState({
      turns: [...turns, { role: "assistant", content: r.reply, tools: r.tool_calls }],
      busy: false,
    });
  } catch (e: unknown) {
    chatStore.setState({ busy: false, error: e instanceof Error ? e.message : String(e) });
  }
}
