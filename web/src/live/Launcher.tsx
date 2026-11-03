import { useState } from "react";

import { api } from "../api/client";
import type { ScenarioInfo } from "../api/messages";
import { baseName } from "../lib/format";
import { useThrottledStore } from "../lib/useThrottledStore";
import { Panel } from "../panels/Panel";
import { liveStore } from "../state/liveStore";
import { refreshStatus } from "../state/useLive";
import { basesFor, defaultBase, nextBase, RANDOM, simulatorLine, SPEED_CHOICES } from "./liveText";

const FIELD =
  "min-w-0 rounded-button border border-hairline bg-scope px-1 py-1 text-13 text-ink-hi disabled:text-ink-low";

/** The scenario launcher (D-184): scenario, actor or team, base, speed, seed, Launch, and Stop
 * (D-192: ends the simulator, keeps the session's incidents). The simulator runs as a separate
 * process; the app keeps the scenario, never who flies (D-182). */
export function Launcher({ installations }: { installations: string[] }) {
  const s = useThrottledStore(liveStore, (st) => ({
    scenarios: st.scenarios,
    installation: st.installation,
    sim: st.status?.simulator,
    launching: st.launching,
    error: st.launchError,
  }));
  const [name, setName] = useState("returning-prober");
  const [actor, setActor] = useState<string | null>("P1");
  const [base, setBase] = useState("BRAVO");
  const [second, setSecond] = useState("CHARLIE");
  const [speed, setSpeed] = useState<number>(20);
  const [seed, setSeed] = useState("");
  const [stopping, setStopping] = useState(false);
  const sc: ScenarioInfo | undefined = s.scenarios.find((x) => x.name === name);
  const bases = basesFor(sc, actor);
  const running = s.sim?.running === true;

  const pickScenario = (n: string) => {
    const next = s.scenarios.find((x) => x.name === n);
    const a = next?.default_actor ?? null;
    const bs = basesFor(next, a);
    const b = defaultBase(bs);
    setName(n);
    setActor(a);
    setBase(b);
    setSecond(nextBase(next?.bases ?? [], b));
  };
  const pickActor = (a: string) => {
    setActor(a);
    const bs = basesFor(sc, a);
    if (!bs.includes(base)) setBase(defaultBase(bs));
  };
  const launch = async () => {
    const st = liveStore.getState();
    st.setLaunch(true);
    try {
      const res = await api.simLaunch({
        scenario: name,
        actor: sc?.actors.length ? actor : null,
        base: actor === RANDOM ? null : base,
        second_base: sc?.second_base ? second : null,
        speed,
        seed: seed.trim() ? Number(seed) : null,
      });
      if (res.base && res.base !== st.installation) st.setInstallation(res.base);
      st.setLaunch(false);
    } catch (e) {
      st.setLaunch(false, e instanceof Error ? e.message : String(e));
    }
    await refreshStatus();
  };
  const stop = async () => {
    setStopping(true);
    try {
      await api.simStop();
      liveStore.getState().setLaunch(false);
    } catch (e) {
      liveStore.getState().setLaunch(false, e instanceof Error ? e.message : String(e));
    }
    setStopping(false);
    await refreshStatus();
  };

  return (
    <Panel id="launcher" title="Launch a scenario" className="shrink-0">
      <form
        aria-label="Scenario launcher"
        className="grid grid-cols-2 gap-x-2 gap-y-1.5 px-3 pb-2.5 text-12 text-ink-mid"
        onSubmit={(e) => {
          e.preventDefault();
          void launch();
        }}
      >
        <label className="col-span-2 flex items-center justify-between gap-2">
          Watching
          <select
            aria-label="Watched installation"
            value={s.installation}
            onChange={(e) => liveStore.getState().setInstallation(e.target.value)}
            className={FIELD}
          >
            {installations.map((i) => (
              <option key={i} value={i}>
                {baseName(i)}
              </option>
            ))}
          </select>
        </label>
        <label className="col-span-2 flex flex-col gap-0.5">
          Scenario
          <select
            aria-label="Scenario"
            value={name}
            onChange={(e) => pickScenario(e.target.value)}
            className={FIELD}
          >
            {s.scenarios.map((x) => (
              <option key={x.name} value={x.name}>
                {x.title}
              </option>
            ))}
          </select>
        </label>
        {sc?.actor_label ? (
          <label className="flex flex-col gap-0.5">
            {sc.actor_label}
            <select
              aria-label={sc.actor_label}
              value={actor ?? ""}
              onChange={(e) => pickActor(e.target.value)}
              className={FIELD}
            >
              {sc.actors.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.id}, {a.nickname}
                </option>
              ))}
              {sc.allow_random ? <option value={RANDOM}>Random (a surprise)</option> : null}
            </select>
          </label>
        ) : null}
        <label className="flex flex-col gap-0.5">
          Base
          <select
            aria-label="Base"
            value={actor === RANDOM ? "" : base}
            disabled={actor === RANDOM}
            onChange={(e) => setBase(e.target.value)}
            className={FIELD}
          >
            {actor === RANDOM ? <option value="">The prober's</option> : null}
            {bases.map((b) => (
              <option key={b} value={b}>
                {baseName(b)}
              </option>
            ))}
          </select>
        </label>
        {sc?.second_base ? (
          <label className="flex flex-col gap-0.5">
            Second base
            <select
              aria-label="Second base"
              value={second}
              onChange={(e) => setSecond(e.target.value)}
              className={FIELD}
            >
              {sc.bases
                .filter((b) => b !== base)
                .map((b) => (
                  <option key={b} value={b}>
                    {baseName(b)}
                  </option>
                ))}
            </select>
          </label>
        ) : null}
        <label className="flex flex-col gap-0.5">
          Speed
          <select
            aria-label="Speed"
            value={speed}
            onChange={(e) => setSpeed(Number(e.target.value))}
            className={FIELD}
          >
            {SPEED_CHOICES.map((v) => (
              <option key={v} value={v}>
                {v}×
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-0.5">
          Seed
          <input
            aria-label="Seed"
            inputMode="numeric"
            pattern="[0-9]*"
            placeholder="automatic"
            value={seed}
            onChange={(e) => setSeed(e.target.value)}
            className={`${FIELD} placeholder:text-ink-low`}
          />
        </label>
        <p className="col-span-2 text-12 text-ink-mid">{sc?.expectation}</p>
        <div className="col-span-2 flex items-center gap-2">
          <button
            type="submit"
            disabled={running || s.launching || !sc}
            className="rounded-button border border-flash px-3 py-1 text-13 text-flash transition-colors duration-(--dur-micro) ease-(--ease-out) hover:bg-hairline disabled:cursor-not-allowed disabled:border-hairline disabled:text-ink-low"
          >
            Launch
          </button>
          <button
            type="button"
            onClick={() => void stop()}
            disabled={!running || stopping}
            title="Stop the simulator; this session's incidents are kept"
            className="rounded-button border border-hairline px-3 py-1 text-13 text-ink-hi transition-colors duration-(--dur-micro) ease-(--ease-out) hover:bg-hairline disabled:cursor-not-allowed disabled:text-ink-low"
          >
            {stopping ? "Stopping" : "Stop"}
          </button>
          <span data-testid="simulator-state" className="min-w-0 truncate text-12 text-ink-mid">
            {simulatorLine(s.sim)}
          </span>
        </div>
        {s.error ? (
          <p role="alert" className="col-span-2 text-12 text-alert">
            {s.error}
          </p>
        ) : null}
      </form>
    </Panel>
  );
}
