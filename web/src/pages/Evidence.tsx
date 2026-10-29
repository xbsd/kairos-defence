import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "../api/client";
import type {
  CaseSummary,
  EvidenceCheck,
  EvidenceDoneLine,
  EvidenceFileLine,
  EvidencePackage,
} from "../api/messages";
import { navigate } from "../app/routes";
import { directorStore } from "../state/directorStore";

function errText(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

function Checks({ checks, testid }: { checks: EvidenceCheck[]; testid: string }) {
  return (
    <ul className="flex flex-col gap-1" data-testid={testid}>
      {checks.map((c) => (
        <li
          key={c.name}
          data-testid="evidence-check"
          data-status={c.status}
          className="flex gap-2 text-13"
        >
          <span
            className={`w-12 font-mono ${c.status === "PASS" ? "text-verified" : c.status === "FAIL" ? "text-alert" : "text-ink-mid"}`}
          >
            {c.status === "PASS" ? "Pass" : c.status === "FAIL" ? "Fail" : "Skip"}
          </span>
          <span className="w-20 text-ink-hi">{c.name}</span>
          <span className="min-w-0 flex-1 text-ink-mid">{c.detail}</span>
        </li>
      ))}
    </ul>
  );
}

/**
 * Evidence (SPEC §15.7, §17.9): "Export evidence package" needs a confirm (rule 8), then shows
 * the server's real per-file hashing progress, the signature and chain checks; "Verify package"
 * re-runs the checks on any exported package.
 */
export function Evidence({ caseId }: { caseId: string | null }) {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [packages, setPackages] = useState<EvidencePackage[]>([]);
  // the export run, keyed by its case: another case shows no stale progress (no reset needed)
  const [run, setRun] = useState<{
    caseId: string;
    files: EvidenceFileLine[];
    done: EvidenceDoneLine | null;
  } | null>(null);
  const files = run && run.caseId === caseId ? run.files : [];
  const done = run && run.caseId === caseId ? run.done : null;
  const [verified, setVerified] = useState<
    Record<string, { passed: boolean; checks: EvidenceCheck[] }>
  >({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const current = cases.find((c) => c.case_id === caseId) ?? null;

  const refresh = useCallback(() => {
    api
      .cases()
      .then(setCases)
      .catch((e: unknown) => setError(errText(e)));
    api
      .evidenceList(caseId ?? undefined)
      .then(setPackages)
      .catch(() => undefined);
  }, [caseId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (!caseId && cases.length) navigate(`/evidence?case=${cases[0]?.case_id ?? ""}`, true);
  }, [caseId, cases]);

  useEffect(() => {
    if (current) directorStore.getState().setFacts({ pending: current.pending });
  }, [current]);

  const exportNow = async () => {
    if (!caseId) return;
    setBusy(true);
    setError(null);
    setRun({ caseId, files: [], done: null });
    try {
      await api.exportEvidence(caseId, (l) => {
        if (l.type === "file")
          setRun((r) => ({ caseId, files: [...(r?.files ?? []), l], done: r?.done ?? null }));
        else if (l.type === "done") setRun((r) => ({ caseId, files: r?.files ?? [], done: l }));
        else setError(l.message);
      });
      refresh();
    } catch (e: unknown) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  };

  const verify = async (dir: string) => {
    setError(null);
    try {
      const v = await api.verifyEvidence(dir);
      setVerified((m) => ({ ...m, [dir]: v }));
    } catch (e: unknown) {
      setError(errText(e));
    }
  };

  const doneDir = done ? (done.dir.split("/").pop() ?? done.dir) : null;
  return (
    <main
      aria-labelledby="evidence-title"
      className="min-h-0 flex-1 overflow-y-auto p-4"
      data-testid="evidence"
    >
      <div className="mx-auto flex max-w-5xl flex-col gap-4">
        <header className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 id="evidence-title" className="text-24 font-bold text-ink-hi">
              Evidence
            </h1>
            <p className="text-15 text-ink-mid">
              A signed package of everything the memory holds about a case, with its chain.
            </p>
          </div>
          <label className="flex flex-col gap-1 text-12 text-ink-mid">
            Case
            <select
              value={caseId ?? ""}
              onChange={(e) => navigate(`/evidence?case=${e.target.value}`)}
              className="rounded-button border border-hairline bg-scope px-2 py-1 text-13 text-ink-hi"
            >
              {cases.map((c) => (
                <option key={c.case_id} value={c.case_id}>
                  {c.case_id}
                </option>
              ))}
            </select>
          </label>
        </header>
        {error ? (
          <p role="alert" className="text-15 text-alert">
            {error}
          </p>
        ) : null}
        <section
          aria-labelledby="export-title"
          className="rounded-panel border border-hairline bg-glass p-4 backdrop-blur-glass"
        >
          <h2 id="export-title" className="text-15 font-bold text-ink-hi">
            Export
          </h2>
          <p className="mt-1 text-13 text-ink-mid" data-testid="evidence-case-state">
            {current
              ? `${current.members.length} member${current.members.length === 1 ? "" : "s"} (${current.members.join(", ")}); ${current.pending} proposed link${current.pending === 1 ? "" : "s"} still waiting for an analyst.`
              : "Choose a case."}
          </p>
          <button
            type="button"
            data-testid="evidence-export"
            disabled={!caseId || busy}
            onClick={() => dialog.current?.showModal?.()}
            className="mt-3 rounded-button border border-flash px-4 py-1.5 text-15 text-flash hover:bg-hairline disabled:border-hairline disabled:text-ink-mid"
          >
            Export evidence package
          </button>
          {files.length ? (
            <table className="mt-3 w-full text-left text-13" data-testid="evidence-files">
              <caption className="sr-only">Files hashed</caption>
              <thead className="text-ink-mid">
                <tr>
                  <th scope="col">File</th>
                  <th scope="col">Bytes</th>
                  <th scope="col">SHA-256</th>
                </tr>
              </thead>
              <tbody>
                {files.map((f) => (
                  <tr key={f.name} data-testid="evidence-file" className="border-t border-hairline">
                    <td className="py-1 text-ink-hi">{f.name}</td>
                    <td className="font-mono text-ink-hi">{f.bytes.toLocaleString("en-US")}</td>
                    <td className="font-mono text-ink-mid">{f.sha256.slice(0, 16)}…</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
          {done ? (
            <div
              className="mt-3 flex flex-col gap-2"
              data-testid="evidence-done"
              data-passed={done.passed}
            >
              <p className={`text-15 ${done.passed ? "text-verified" : "text-alert"}`}>
                {done.passed ? "Package verified" : "Verification failed"}: {doneDir}, ledger row #
                {done.seq}
                {done.signed ? ", signed" : ", unsigned"}
              </p>
              <Checks checks={done.checks} testid="evidence-checks" />
            </div>
          ) : null}
        </section>
        <section
          aria-labelledby="packages-title"
          className="rounded-panel border border-hairline bg-glass p-4 backdrop-blur-glass"
        >
          <h2 id="packages-title" className="text-15 font-bold text-ink-hi">
            Packages
          </h2>
          {packages.length ? (
            <ul className="mt-2 flex flex-col gap-3" data-testid="evidence-packages">
              {packages.map((p) => (
                <li
                  key={p.dir}
                  data-testid="evidence-package"
                  className="flex flex-col gap-1.5 border-t border-hairline pt-2"
                >
                  <div className="flex flex-wrap items-center gap-3 text-13">
                    <span className="text-ink-hi">{p.dir}</span>
                    <span className="font-mono text-ink-mid">
                      manifest {p.manifest_sha256?.slice(0, 12) ?? "–"}
                    </span>
                    <button
                      type="button"
                      onClick={() => void verify(p.dir)}
                      className="ml-auto rounded-button border border-hairline px-3 py-1 text-13 text-ink-hi hover:border-verified"
                    >
                      Verify package
                    </button>
                  </div>
                  {verified[p.dir] ? (
                    <div data-testid="verify-result" data-passed={verified[p.dir]?.passed}>
                      <Checks checks={verified[p.dir]?.checks ?? []} testid="verify-checks" />
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-1 text-13 text-ink-mid">No package exported for this case yet.</p>
          )}
        </section>
      </div>
      <dialog
        ref={dialog}
        aria-labelledby="export-confirm-title"
        className="m-auto w-[28rem] rounded-panel border border-hairline bg-scope p-4 text-ink-hi backdrop:bg-scope/70"
      >
        <h2 id="export-confirm-title" className="text-15 font-bold">
          Export the evidence package for {caseId}?
        </h2>
        <p className="mt-2 text-13 text-ink-mid">
          You approve this export as analyst "demo". The package is signed and the export is
          appended to the ledger.
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={() => dialog.current?.close?.()}
            className="rounded-button border border-hairline px-3 py-1 text-13"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => {
              dialog.current?.close?.();
              void exportNow();
            }}
            className="rounded-button border border-flash px-3 py-1 text-13 text-flash"
          >
            Approve and export
          </button>
        </div>
      </dialog>
    </main>
  );
}
