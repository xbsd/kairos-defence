import { useState } from "react";

import { useThrottledStore } from "../lib/useThrottledStore";
import { chatStore, sendChat, setChatOpen } from "./chatStore";

/** The command bar's "Ask" button: present only when the server enables chat (§18.3). */
export function AskButton() {
  const s = useThrottledStore(chatStore, (st) => ({ on: !!st.status?.enabled, open: st.open }), 4);
  if (!s.on) return null;
  return (
    <button
      type="button"
      aria-pressed={s.open}
      aria-controls="chat-panel"
      onClick={() => setChatOpen(!s.open)}
      title="Ask about flights, reports and cases: answers cite the tools' ids"
      className={`rounded-button border px-3 py-1 text-13 transition-colors duration-(--dur-micro) ease-(--ease-out) ${
        s.open ? "border-flash text-flash" : "border-hairline text-ink-mid hover:text-ink-hi"
      }`}
    >
      Ask
    </button>
  );
}

/**
 * The chat slide-over (§18.3): the assistant answers only from the §18.1 tool results and names
 * the incident, report and ledger ids it used; it links flights, never people, and proposes but
 * never commits. Each reply lists the tool calls behind it.
 */
export function ChatPanel() {
  const s = useThrottledStore(chatStore, (st) => st, 10);
  const [text, setText] = useState("");
  if (!s.status?.enabled || !s.open) return null;
  return (
    <aside
      id="chat-panel"
      role="dialog"
      aria-label="Ask Kairos Defense"
      data-testid="chat-panel"
      className="fixed top-12 right-0 bottom-0 z-40 flex w-[28rem] max-w-full flex-col border-l border-hairline bg-glass backdrop-blur-glass"
    >
      <header className="flex items-baseline justify-between gap-2 border-b border-hairline px-4 py-3">
        <h2 className="text-15 font-bold text-ink-hi">Ask</h2>
        <span className="truncate text-12 text-ink-mid">
          {s.status.provider}
          {s.status.model ? ` · ${s.status.model}` : ""}
        </span>
        <button
          type="button"
          onClick={() => setChatOpen(false)}
          className="rounded-button px-2 py-1 text-13 text-ink-mid hover:bg-hairline hover:text-ink-hi"
        >
          Close
        </button>
      </header>
      <p className="px-4 py-2 text-12 text-ink-mid">
        Answers come only from Kairos Defense&apos;s tools and cite their ids. Flights, never
        people. It can propose; only you approve.
      </p>
      <ol
        aria-label="Conversation"
        className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 py-2"
      >
        {s.turns.map((t, i) => (
          <li key={i} data-testid={`chat-${t.role}`} className="flex flex-col gap-1">
            <span className="text-12 text-ink-mid">
              {t.role === "user" ? "You" : "Kairos Defense"}
            </span>
            <p className="text-13 whitespace-pre-wrap text-ink-hi">{t.content}</p>
            {t.tools?.length ? (
              <ul aria-label="Tool calls" className="flex flex-col gap-1">
                {t.tools.map((c, k) => (
                  <li key={k} data-testid="chat-tool" className="font-mono text-12 text-ink-mid">
                    {c.name}(
                    {Object.entries(c.arguments)
                      .map(([a, v]) => `${a}=${JSON.stringify(v)}`)
                      .join(", ")}
                    )
                  </li>
                ))}
              </ul>
            ) : null}
          </li>
        ))}
        {s.busy ? <li className="text-13 text-ink-mid">Working through the tools</li> : null}
      </ol>
      {s.error ? (
        <p role="alert" className="px-4 py-1 text-13 text-alert">
          {s.error}
        </p>
      ) : null}
      <form
        className="flex gap-2 border-t border-hairline p-3"
        onSubmit={(e) => {
          e.preventDefault();
          void sendChat(text);
          setText("");
        }}
      >
        <label htmlFor="chat-input" className="sr-only">
          Question
        </label>
        <textarea
          id="chat-input"
          rows={2}
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="min-w-0 flex-1 resize-none rounded-button border border-hairline bg-scope px-2 py-1 text-13 text-ink-hi"
          placeholder="Which past flights match DEMO-BRAVO-0828?"
        />
        <button
          type="submit"
          disabled={s.busy || !text.trim()}
          className="rounded-button border border-hairline px-3 py-1 text-13 text-ink-hi hover:bg-hairline disabled:cursor-not-allowed disabled:text-ink-low"
        >
          Send
        </button>
      </form>
    </aside>
  );
}
