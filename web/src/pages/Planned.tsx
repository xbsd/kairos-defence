import { PLANNED, type PlannedPage } from "../app/routes";

/** A page another phase builds: one plain sentence, no fake data (rule 10). */
export function Planned({ page }: { page: PlannedPage }) {
  const p = PLANNED[page];
  return (
    <main aria-labelledby="planned-title" className="grid flex-1 place-items-center p-8">
      <div className="max-w-md text-center">
        <h1 id="planned-title" className="text-18 font-bold text-ink-hi">
          {p.title}
        </h1>
        <p className="mt-2 text-15 text-ink-mid">
          The {p.title.toLowerCase()} arrives in phase {p.phase}. Live watch is ready now.
        </p>
      </div>
    </main>
  );
}

export function NotFound({ path }: { path: string }) {
  return (
    <main aria-labelledby="nf-title" className="grid flex-1 place-items-center p-8">
      <div className="max-w-md text-center">
        <h1 id="nf-title" className="text-18 font-bold text-ink-hi">
          No page at {path}
        </h1>
        <p className="mt-2 text-15 text-ink-mid">Use the Pages menu to open Live watch.</p>
      </div>
    </main>
  );
}
