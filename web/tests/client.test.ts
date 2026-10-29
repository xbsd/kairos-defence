import { afterEach, describe, expect, it, vi } from "vitest";

import { ANALYST, ApiError, api, readNdjson, setFetch } from "../src/api/client";
import type { EvidenceLine } from "../src/api/messages";

afterEach(() => setFetch((...a) => fetch(...a)));

describe("api client", () => {
  it("posts a link decision with the proposal, decision, analyst and clock", async () => {
    const f = vi.fn(
      async () => new Response(JSON.stringify({ block: { seq: 9 } }), { status: 200 }),
    );
    setFetch(f as unknown as typeof fetch);
    await api.decideLink("CASE-P1-DELTA-260419", 4683, "approve", "2026-08-29T02:41:40.000Z");
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/cases/CASE-P1-DELTA-260419/links");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({
      proposal_seq: 4683,
      decision: "approve",
      analyst: ANALYST,
      clock: "2026-08-29T02:41:40.000Z",
    });
    expect(ANALYST).toBe("demo");
  });

  it("errors carry the server's message", async () => {
    setFetch(
      (async () =>
        new Response(JSON.stringify({ detail: "proposal 7 is already decided" }), {
          status: 409,
        })) as unknown as typeof fetch,
    );
    const err = await api.decideLink("C", 7, "approve", "t").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).status).toBe(409);
    expect((err as ApiError).message).toBe("proposal 7 is already decided");
  });

  it("parses evidence NDJSON line by line", async () => {
    const lines = [
      { type: "file", name: "case.json", bytes: 10, sha256: "a", i: 1, n: 2 },
      {
        type: "done",
        dir: "d",
        manifest_sha256: "m",
        seq: 5,
        head_seq: 4,
        signed: true,
        checks: [],
        passed: true,
      },
    ];
    const body = new ReadableStream({
      start(c) {
        const enc = new TextEncoder();
        const text = lines.map((l) => JSON.stringify(l)).join("\n") + "\n";
        c.enqueue(enc.encode(text.slice(0, 17)));
        c.enqueue(enc.encode(text.slice(17)));
        c.close();
      },
    });
    const got: EvidenceLine[] = [];
    await readNdjson(new Response(body), (l: EvidenceLine) => got.push(l));
    expect(got.map((l) => l.type)).toEqual(["file", "done"]);
  });
});
