import { CommandBar } from "./CommandBar";

/**
 * Phase 0 placeholder for Live watch. Nothing here is animated or numeric: the theater only ever
 * draws real stream events (CLAUDE.md rule 10), and none are connected until phase 7.
 */
export function App() {
  return (
    <div className="flex h-full flex-col bg-scope">
      <CommandBar trail={["Live watch"]} replayClock={null} speed={1} live={false} />
      <main
        aria-label="Live theater"
        className="relative grid flex-1 place-items-center overflow-hidden"
      >
        <div className="max-w-md text-center">
          <h1 className="text-18 font-bold text-ink-mid">No replay loaded</h1>
          <p className="mt-2 text-13 text-balance text-ink-mid">
            The live theater draws only real stream events. None are connected yet.
          </p>
        </div>
      </main>
    </div>
  );
}
