import { useEffect, useState } from "react";

import { api } from "../api/client";
import { navigate } from "../app/routes";

/** `/`: open Live watch for the first live single-track incident. */
export function Home() {
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    api
      .liveIncidents()
      .then((list) => {
        if (!alive) return;
        const first = list.find((i) => !i.is_swarm) ?? list[0];
        if (first) navigate(`/live/${first.incident_id}`, true);
        else setError("No live incident in the data. Run make data index models.");
      })
      .catch((e: unknown) => alive && setError(String(e instanceof Error ? e.message : e)));
    return () => {
      alive = false;
    };
  }, []);
  return (
    <main aria-labelledby="home-title" className="grid flex-1 place-items-center p-8">
      <div className="max-w-md text-center">
        <h1 id="home-title" className="text-18 font-bold text-ink-hi">
          {error ? "No replay loaded" : "Opening Live watch"}
        </h1>
        {error ? <p className="mt-2 text-15 text-ink-mid">{error}</p> : null}
      </div>
    </main>
  );
}
