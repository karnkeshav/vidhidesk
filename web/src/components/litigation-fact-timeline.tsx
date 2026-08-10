"use client";

import React, { useRef, useState } from "react";
import { Calendar, FileText, Paperclip, Plus, Trash2, UploadCloud } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export interface FactItem {
  id: string;
  event_date?: string | null;
  fact_summary: string;
  exhibit_number?: string | null;
  document_title?: string | null;
  relevance_notes?: string | null;
  file_url?: string | null;
  file_name?: string | null;
  mime_type?: string | null;
  created_at?: string;
}

interface LitigationFactTimelineProps {
  facts: FactItem[];
  onAddFact: (factData: {
    event_date?: string;
    fact_summary: string;
    exhibit_number?: string;
    document_title?: string;
    relevance_notes?: string;
  }) => Promise<void>;
  onUploadFile: (
    file: File,
    fields: { event_date?: string; exhibit_number?: string; document_title?: string; relevance_notes?: string }
  ) => Promise<void>;
  onDeleteFact: (factId: string) => Promise<void>;
}

export function LitigationFactTimeline({
  facts,
  onAddFact,
  onUploadFile,
  onDeleteFact,
}: LitigationFactTimelineProps) {
  const [showAddForm, setShowAddForm] = useState(false);
  const [eventDate, setEventDate] = useState("");
  const [factSummary, setFactSummary] = useState("");
  const [exhibitNumber, setExhibitNumber] = useState("");
  const [documentTitle, setDocumentTitle] = useState("");
  const [relevanceNotes, setRelevanceNotes] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const resetForm = () => {
    setEventDate("");
    setFactSummary("");
    setExhibitNumber("");
    setDocumentTitle("");
    setRelevanceNotes("");
    setSelectedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setUploadError(null);

    // A selected file makes this an "Upload Evidence" action (real
    // document, multipart) rather than a "Record Facts" action (text
    // narrative only) — both write to the same fact/exhibit timeline,
    // they just differ in whether a document backs the entry.
    if (selectedFile) {
      setSubmitting(true);
      try {
        await onUploadFile(selectedFile, {
          event_date: eventDate || undefined,
          exhibit_number: exhibitNumber.trim() || undefined,
          document_title: documentTitle.trim() || undefined,
          relevance_notes: relevanceNotes.trim() || undefined,
        });
        resetForm();
        setShowAddForm(false);
      } catch (err) {
        setUploadError(err instanceof Error ? err.message : String(err));
      } finally {
        setSubmitting(false);
      }
      return;
    }

    if (!factSummary.trim()) return;
    setSubmitting(true);
    try {
      await onAddFact({
        event_date: eventDate || undefined,
        fact_summary: factSummary.trim(),
        exhibit_number: exhibitNumber.trim() || undefined,
        document_title: documentTitle.trim() || undefined,
        relevance_notes: relevanceNotes.trim() || undefined,
      });
      resetForm();
      setShowAddForm(false);
    } catch (err) {
      console.error("Failed to add fact entry", err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-sans text-sm font-semibold uppercase tracking-wider text-[#081534]">
            Facts & Exhibit Timeline
          </h3>
          <p className="font-serif text-xs text-[#45464E]">
            Chronological sequence of material facts and marked exhibit documents
          </p>
        </div>
        <Button
          onClick={() => setShowAddForm(!showAddForm)}
          className="h-8 gap-1.5 rounded-sm bg-[#081534] font-sans text-xs font-semibold text-white hover:bg-[#1E2A4A]"
        >
          <Plus className="h-3.5 w-3.5" />
          {showAddForm ? "Cancel" : "Add Fact Entry"}
        </Button>
      </div>

      {showAddForm && (
        <form
          onSubmit={handleCreate}
          className="rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] p-4 space-y-3 font-sans text-xs"
        >
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div>
              <label className="font-semibold text-[#081534]">Event Date</label>
              <Input
                type="date"
                value={eventDate}
                onChange={(e) => setEventDate(e.target.value)}
                className="h-8 rounded-sm border-[#E4E2DD] bg-white text-xs text-[#1A1A1A]"
              />
            </div>
            <div>
              <label className="font-semibold text-[#081534]">Exhibit No. (Optional)</label>
              <Input
                type="text"
                placeholder="e.g. Exhibit P-1"
                value={exhibitNumber}
                onChange={(e) => setExhibitNumber(e.target.value)}
                className="h-8 rounded-sm border-[#E4E2DD] bg-white text-xs text-[#1A1A1A]"
              />
            </div>
            <div>
              <label className="font-semibold text-[#081534]">Document Title (Optional)</label>
              <Input
                type="text"
                placeholder="e.g. Sub-Lease Agreement"
                value={documentTitle}
                onChange={(e) => setDocumentTitle(e.target.value)}
                className="h-8 rounded-sm border-[#E4E2DD] bg-white text-xs text-[#1A1A1A]"
              />
            </div>
          </div>

          <div>
            <label className="font-semibold text-[#081534]">
              Fact Narrative Summary {selectedFile ? "(Optional — a file is attached)" : "*"}
            </label>
            <textarea
              rows={2}
              required={!selectedFile}
              placeholder="State the material fact, breach, or event concise summary..."
              value={factSummary}
              onChange={(e) => setFactSummary(e.target.value)}
              className="w-full rounded-sm border border-[#E4E2DD] bg-white p-2 text-xs text-[#1A1A1A] focus:outline-none focus:ring-1 focus:ring-[#081534]"
            />
          </div>

          <div>
            <label className="font-semibold text-[#081534]">Relevance / Evidentiary Notes (Optional)</label>
            <Input
              type="text"
              placeholder="e.g. Proves breach of notice period clause"
              value={relevanceNotes}
              onChange={(e) => setRelevanceNotes(e.target.value)}
              className="h-8 rounded-sm border-[#E4E2DD] bg-white text-xs text-[#1A1A1A]"
            />
          </div>

          <div className="rounded-sm border border-dashed border-[#C6C6CF] bg-white p-3">
            <label className="flex items-center gap-1.5 font-semibold text-[#081534]">
              <UploadCloud className="h-3.5 w-3.5" />
              Upload Evidence Document (Optional)
            </label>
            <p className="mt-0.5 text-[10px] text-[#76777F]">
              PDF, DOC/DOCX, JPG, PNG, or WEBP, up to 10MB. Attaching a file uploads the actual exhibit, not just a
              text label.
            </p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.doc,.docx,image/jpeg,image/png,image/webp,application/pdf"
              onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
              className="mt-2 w-full text-[11px] text-[#1A1A1A]"
            />
            {selectedFile && (
              <p className="mt-1 flex items-center gap-1 text-[10px] font-medium text-[#3D5A3D]">
                <Paperclip className="h-3 w-3" />
                {selectedFile.name} ({(selectedFile.size / 1024).toFixed(0)} KB)
              </p>
            )}
            {uploadError && <p className="mt-1 text-[10px] font-medium text-[#7A2A2A]">{uploadError}</p>}
          </div>

          <div className="flex justify-end gap-2 pt-1">
            <Button
              type="button"
              variant="outline"
              onClick={() => setShowAddForm(false)}
              className="h-7 rounded-sm border-[#E4E2DD] text-xs text-[#45464E]"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={submitting}
              className="h-7 rounded-sm bg-[#081534] text-xs font-semibold text-white hover:bg-[#1E2A4A]"
            >
              {submitting ? (selectedFile ? "Uploading..." : "Saving...") : selectedFile ? "Upload Evidence" : "Save Fact Entry"}
            </Button>
          </div>
        </form>
      )}

      {facts.length === 0 ? (
        <div className="rounded-sm border border-dashed border-[#E4E2DD] p-8 text-center font-sans text-xs text-[#76777F]">
          No chronological facts or exhibit items recorded yet. Click &quot;Add Fact Entry&quot; to build the case timeline.
        </div>
      ) : (
        <div className="relative border-l border-[#E4E2DD] ml-3 pl-5 space-y-4">
          {facts.map((fact) => (
            <div key={fact.id} className="relative rounded-sm border border-[#E4E2DD] bg-white p-3.5 font-sans text-xs">
              <span className="absolute -left-7 top-4 h-3 w-3 rounded-full border-2 border-[#081534] bg-white" />

              <div className="flex items-start justify-between gap-2">
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2 font-semibold text-[#081534]">
                    {fact.event_date && (
                      <span className="flex items-center gap-1 text-[11px] font-medium text-[#45464E]">
                        <Calendar className="h-3 w-3 text-[#081534]" />
                        {fact.event_date}
                      </span>
                    )}
                    {fact.exhibit_number && (
                      <span className="rounded-xs border border-[#C6C6CF] bg-[#F0EEE9] px-1.5 py-0.5 text-[10px] uppercase font-bold text-[#081534]">
                        {fact.exhibit_number}
                      </span>
                    )}
                    {fact.document_title && (
                      <span className="flex items-center gap-1 text-xs text-[#081534]">
                        <FileText className="h-3 w-3 text-[#76777F]" />
                        {fact.document_title}
                      </span>
                    )}
                  </div>

                  <p className="font-serif text-xs leading-relaxed text-[#1A1A1A]">
                    {fact.fact_summary}
                  </p>

                  {fact.relevance_notes && (
                    <p className="font-serif text-[11px] italic text-[#76777F]">
                      Relevance: {fact.relevance_notes}
                    </p>
                  )}

                  {fact.file_url && (
                    <a
                      href={fact.file_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-[11px] font-medium text-[#081534] underline"
                    >
                      <Paperclip className="h-3 w-3" />
                      {fact.file_name || "View uploaded file"}
                    </a>
                  )}
                </div>

                <button
                  onClick={() => onDeleteFact(fact.id)}
                  className="text-[#76777F] hover:text-[#7A2A2A]"
                  title="Delete Fact Entry"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
