// A fake fetch that answers by URL (the page tests' server).
import { vi } from "vitest";

import { setFetch } from "../src/api/client";

export type Handler = (url: string, init?: RequestInit) => unknown;

export function routeFetch(routes: [RegExp, Handler][]) {
  const f = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    for (const [re, h] of routes) {
      if (re.test(url)) {
        const body = h(url, init);
        if (body instanceof Response) return body;
        return new Response(JSON.stringify(body), { status: 200 });
      }
    }
    return new Response(JSON.stringify({ detail: `no route ${url}` }), { status: 404 });
  });
  setFetch(f as unknown as typeof fetch);
  return f;
}

export function calls(f: ReturnType<typeof routeFetch>): [string, RequestInit | undefined][] {
  return f.mock.calls.map((c) => [String(c[0]), c[1] as RequestInit | undefined]);
}
