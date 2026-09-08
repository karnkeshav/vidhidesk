"use client";

import { CourtCaseTracking } from "@/lib/api";

export function FiledDocuments({ tracking }: { tracking: CourtCaseTracking | null }) {
  if (!tracking?.filed_documents || tracking.filed_documents.length === 0) {
    return (
      <div className="rounded-sm border border-[#E4E2DD] bg-white p-5 space-y-3 font-sans text-xs">
        <h3 className="font-sans text-sm font-semibold uppercase tracking-wider text-[#081534]">
          Filed Documents
        </h3>
        <p className="font-serif text-xs text-[#76777F]">No documents filed in this case yet.</p>
      </div>
    );
  }

  return (
    <div className="rounded-sm border border-[#E4E2DD] bg-white p-5 space-y-4 font-sans text-xs">
      <div className="flex items-center justify-between">
        <h3 className="font-sans text-sm font-semibold uppercase tracking-wider text-[#081534]">
          Filed Documents ({tracking.filed_documents.length})
        </h3>
      </div>

      <div className="divide-y divide-[#E4E2DD]">
        {tracking.filed_documents.map((doc, idx) => (
          <DocumentRow key={idx} doc={doc} />
        ))}
      </div>
    </div>
  );
}

function DocumentRow({ doc }: { doc: Record<string, unknown> }) {
  // Extract common fields that eCourts API typically returns for documents
  const documentName = getString(doc.documentName) || getString(doc.name) || "Untitled Document";
  const filingDate = getString(doc.filingDate) || getString(doc.dateOfFiling);
  const filedBy = getString(doc.filedBy) || getString(doc.filledBy) || getString(doc.party);
  const documentType = getString(doc.documentType) || getString(doc.type);
  const documentUrl = getString(doc.documentUrl) || getString(doc.url);
  const status = getString(doc.status);

  return (
    <div className="py-2.5 space-y-1.5">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <p className="font-semibold text-[#081534]">{documentName}</p>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {documentType && (
              <Badge label="Type" value={documentType} />
            )}
            {filedBy && (
              <Badge label="Filed by" value={filedBy} />
            )}
            {status && (
              <Badge label="Status" value={status} />
            )}
          </div>
        </div>
      </div>

      {filingDate && (
        <p className="font-serif text-[11px] text-[#76777F]">
          Filed: {new Date(filingDate).toLocaleDateString()}
        </p>
      )}

      {documentUrl && isAbsoluteUrl(documentUrl) && (
        <div className="flex items-center gap-1.5 py-0.5">
          <a
            href={documentUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 rounded-xs border border-[#E4E2DD] bg-[#FBF9F4] px-1.5 py-0.5 font-mono text-[10px] text-[#081534] hover:bg-[#F0EEE9]"
          >
            📎 View Document
          </a>
        </div>
      )}
      {documentUrl && !isAbsoluteUrl(documentUrl) && (
        <p className="font-serif text-[11px] text-[#76777F]">
          File reference: {documentUrl} (not yet available for download from the court&apos;s system)
        </p>
      )}
    </div>
  );
}

function Badge({ label, value }: { label: string; value: string }) {
  return (
    <span className="rounded-xs border border-[#D0D0D8] bg-[#F5F5F7] px-1.5 py-0.5 text-[9px] font-semibold text-[#45464E] uppercase">
      {label}: {value}
    </span>
  );
}

function getString(value: unknown): string | null {
  if (typeof value === "string") return value || null;
  if (typeof value === "number") return String(value);
  return null;
}

// eCourts responses have been observed to return a bare filename (e.g.
// "order-1.pdf") with no host at all instead of a real link -- rendering
// that as an <a href> produces a dead link resolving against this app's
// own domain. Only ever link out for a genuine absolute http(s) URL.
function isAbsoluteUrl(value: string): boolean {
  return /^https?:\/\//i.test(value);
}
