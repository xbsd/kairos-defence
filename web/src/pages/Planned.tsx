// Every planned page is built (phase 9 removed the last placeholder, the Swarm view); this file
// keeps the not-found page.

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
