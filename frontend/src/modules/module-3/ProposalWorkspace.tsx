import { useEffect, useRef } from "react";
import { ProposalComplianceReport } from "../../portals/student/modules/ProposalComplianceReport";
import { ProposalLifecycleWorkspace } from "../../portals/student/modules/ProposalLifecycleWorkspace";

export function ProposalWorkspace({ api }: { api: string }) {
  const latestDocument = useRef<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    const checkForUpload = async () => {
      try {
        const response = await fetch(`${api}/api/v1/proposals/mine`, { credentials: "include" });
        if (!response.ok || cancelled) return;
        const proposals = await response.json() as Array<{ id: number; document?: { id?: number; version?: number } | null }>;
        const current = proposals.find((item) => item.document) ?? null;
        if (!current || cancelled) return;
        const key = `${current.id}:${current.document?.version ?? current.document?.id ?? "latest"}`;
        if (latestDocument.current && latestDocument.current !== key) window.dispatchEvent(new CustomEvent("module3-proposal-uploaded", { detail: { id: current.id } }));
        latestDocument.current = key;
      } catch {
        // The lifecycle workspace owns the visible error state.
      }
    };
    void checkForUpload();
    const timer = window.setInterval(() => { void checkForUpload(); }, 2500);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [api]);

  return <div className="module3-proposal-stack">
    <ProposalLifecycleWorkspace api={api} />
    <section aria-labelledby="module3-compliance-heading" className="module3-compliance-panel">
      <div className="module3-compliance-panel__intro">
        <p className="student-overview__eyebrow">Module 3 · Proposal compliance</p>
        <h2 id="module3-compliance-heading">Compliance report</h2>
        <p>Your uploaded proposal is compared with the active university template here. A new upload creates a fresh comparison after extraction.</p>
      </div>
      <ProposalComplianceReport api={api} autoRun embedded />
    </section>
  </div>;
}
