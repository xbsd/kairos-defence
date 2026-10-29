import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { setFetch } from "../src/api/client";
import { AskButton, ChatPanel } from "../src/chat/ChatPanel";
import { chatStore, loadChatStatus } from "../src/chat/chatStore";

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const flush = () => act(() => new Promise((r) => setTimeout(r, 120)));

afterEach(() => {
  chatStore.setState({ status: null, open: false, turns: [], busy: false, error: null });
  setFetch((...args) => fetch(...args));
});

describe("Chat slide-over (§18.3)", () => {
  it("stays hidden when the provider is none, or the route is missing", async () => {
    setFetch(async () => json({ enabled: false, provider: "none", model: "", tools: [] }));
    render(
      <>
        <AskButton />
        <ChatPanel />
      </>,
    );
    await act(() => loadChatStatus());
    await flush();
    expect(screen.queryByRole("button", { name: "Ask" })).toBeNull();
    expect(screen.queryByTestId("chat-panel")).toBeNull();
    setFetch(async () => json({ detail: "Not Found" }, 404));
    await act(() => loadChatStatus());
    await flush();
    expect(chatStore.getState().status?.enabled).toBe(false);
    expect(screen.queryByRole("button", { name: "Ask" })).toBeNull();
  });

  it("asks through the server's tool loop and shows the reply with its tool calls", async () => {
    const sent: unknown[] = [];
    setFetch(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/chat/status"))
        return json({
          enabled: true,
          provider: "anthropic",
          model: "test-model",
          tools: ["find_similar_flights"],
        });
      sent.push(JSON.parse(String(init?.body)));
      return json({
        reply: "P1-DELTA-260419 ranks first (score 1.00).",
        tool_calls: [
          {
            name: "find_similar_flights",
            arguments: { incident_id: "DEMO-BRAVO-0828", window_s: 120 },
            result: [{ incident_id: "P1-DELTA-260419" }],
          },
        ],
        provider: "anthropic",
        model: "test-model",
      });
    });
    render(
      <>
        <AskButton />
        <ChatPanel />
      </>,
    );
    await act(() => loadChatStatus());
    await flush();
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await flush();
    expect(screen.getByTestId("chat-panel")).toHaveTextContent("anthropic · test-model");
    fireEvent.change(screen.getByLabelText("Question"), {
      target: { value: "Which past flights match DEMO-BRAVO-0828?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await flush();
    expect(sent).toEqual([
      { messages: [{ role: "user", content: "Which past flights match DEMO-BRAVO-0828?" }] },
    ]);
    expect(screen.getByTestId("chat-assistant")).toHaveTextContent("P1-DELTA-260419 ranks first");
    expect(screen.getByTestId("chat-tool")).toHaveTextContent(
      'find_similar_flights(incident_id="DEMO-BRAVO-0828", window_s=120)',
    );
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    await flush();
    expect(screen.queryByTestId("chat-panel")).toBeNull();
  });
});
