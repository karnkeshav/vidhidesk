"use client";

import { useState, type FormEvent } from "react";
import { Plus } from "lucide-react";
import { OrderOut } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Real orders (api/app/routers/litigation.py's /matters/{id}/orders,
 * source='manual' unless a future eCourts order sync writes source=
 * 'ecourts'). Deliberately does NOT claim OCR/confidence scores -- no
 * OCR pipeline exists in this codebase; raw_text is whatever text was
 * typed or pasted in when the order was logged. */
export function OrdersSection({
  orders,
  onAddOrder,
}: {
  orders: OrderOut[];
  onAddOrder: (input: { order_date?: string; court?: string; raw_text?: string }) => Promise<void>;
}) {
  const [showForm, setShowForm] = useState(false);
  const [orderDate, setOrderDate] = useState("");
  const [court, setCourt] = useState("");
  const [rawText, setRawText] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await onAddOrder({ order_date: orderDate || undefined, court: court || undefined, raw_text: rawText || undefined });
      setOrderDate("");
      setCourt("");
      setRawText("");
      setShowForm(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="rounded-sm border border-[#E4E2DD] bg-white p-5 space-y-4 font-sans text-xs">
      <div className="flex items-center justify-between">
        <h3 className="font-sans text-sm font-semibold uppercase tracking-wider text-[#081534]">
          Orders ({orders.length})
        </h3>
        <Button
          onClick={() => setShowForm((v) => !v)}
          className="h-8 gap-1.5 rounded-sm bg-[#081534] text-xs font-semibold text-white hover:bg-[#1E2A4A]"
        >
          <Plus className="h-3.5 w-3.5" />
          Log Order
        </Button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="space-y-2 rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] p-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="font-semibold text-[#081534]">Order Date</label>
              <input
                type="date"
                value={orderDate}
                onChange={(e) => setOrderDate(e.target.value)}
                className="h-8 w-full rounded-sm border border-[#E4E2DD] bg-white px-2 text-xs"
              />
            </div>
            <div>
              <label className="font-semibold text-[#081534]">Court</label>
              <input
                type="text"
                value={court}
                onChange={(e) => setCourt(e.target.value)}
                className="h-8 w-full rounded-sm border border-[#E4E2DD] bg-white px-2 text-xs"
              />
            </div>
          </div>
          <div>
            <label className="font-semibold text-[#081534]">Order Text</label>
            <textarea
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
              rows={4}
              className="w-full rounded-sm border border-[#E4E2DD] bg-white px-2 py-1.5 text-xs"
            />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="outline" onClick={() => setShowForm(false)} className="h-7 text-xs">
              Cancel
            </Button>
            <Button type="submit" disabled={saving} className="h-7 bg-[#081534] text-xs font-semibold text-white">
              {saving ? "Saving..." : "Save Order"}
            </Button>
          </div>
        </form>
      )}

      {orders.length === 0 ? (
        <p className="font-serif text-xs text-[#76777F]">No orders logged for this matter yet.</p>
      ) : (
        <div className="divide-y divide-[#E4E2DD]">
          {orders.map((o) => (
            <div key={o.id} className="py-2.5 space-y-1">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-[#081534]">
                  {o.order_date ? new Date(o.order_date).toLocaleDateString() : "Undated order"}
                </span>
                <span
                  className={cn(
                    "rounded-xs px-1.5 py-0.5 text-[10px] font-bold uppercase",
                    o.status === "active" && "bg-[#F0EEE9] text-[#45464E]",
                    o.status === "complied" && "bg-[#D4EDDA] text-[#155724]",
                    o.status === "superseded" && "bg-[#FFF5F5] text-[#7A2A2A]"
                  )}
                >
                  {o.status}
                </span>
                <span className="rounded-xs border border-[#C6C6CF] px-1 text-[9px] uppercase text-[#76777F]">
                  {o.source}
                </span>
              </div>
              {o.court && <p className="font-serif text-[11px] text-[#45464E]">{o.court}</p>}
              {o.file_url && isAbsoluteUrl(o.file_url) && (
                <div className="flex items-center gap-1.5 py-0.5">
                  <a
                    href={o.file_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 rounded-xs border border-[#E4E2DD] bg-[#FBF9F4] px-1.5 py-0.5 font-mono text-[10px] text-[#081534] hover:bg-[#F0EEE9]"
                  >
                    📄 View File
                  </a>
                </div>
              )}
              {o.file_url && !isAbsoluteUrl(o.file_url) && (
                <p className="font-serif text-[11px] text-[#76777F]">
                  File reference: {o.file_url} (not yet available for download from the court&apos;s system)
                </p>
              )}
              {o.raw_text && <p className="font-serif text-[11px] text-[#76777F] whitespace-pre-wrap">{o.raw_text}</p>}
              {o.ai_extracted_directions.length > 0 && (
                <ul className="ml-4 list-disc font-serif text-[11px] text-[#45464E]">
                  {o.ai_extracted_directions.map((d, i) => (
                    <li key={i}>
                      {d.direction}
                      {d.deadline && ` (by ${d.deadline})`}
                      {d.complied && " — complied"}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// eCourts responses have been observed to return a bare filename (e.g.
// "order-1.pdf") with no host at all instead of a real link -- rendering
// that as an <a href> produces a dead link resolving against this app's
// own domain. Only ever link out for a genuine absolute http(s) URL.
function isAbsoluteUrl(value: string): boolean {
  return /^https?:\/\//i.test(value);
}
