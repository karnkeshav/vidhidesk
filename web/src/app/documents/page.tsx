"use client";

import { useState } from "react";
import { AuthedShell } from "@/components/authed-shell";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Download, Search, Plus, FolderOpen } from "lucide-react";

export default function DocumentsPage() {
  const [searchQuery, setSearchQuery] = useState("");

  const sampleDocuments = [
    {
      id: "doc-1",
      title: "Non-Disclosure Agreement — Acme Corp (Draft v2.docx)",
      matter: "Acme Corp NDA",
      category: "Contracts",
      size: "48 KB",
      updated_at: "2 Aug 2026",
    },
    {
      id: "doc-2",
      title: "Service Agreement — Tata Consultancy (Reviewed.docx)",
      matter: "Tata Service Dispute",
      category: "Contracts",
      size: "62 KB",
      updated_at: "1 Aug 2026",
    },
    {
      id: "doc-3",
      title: "RERA Project Registration Compliance Statement.pdf",
      matter: "RERA Compliance #402",
      category: "RERA",
      size: "128 KB",
      updated_at: "30 Jul 2026",
    },
  ];

  const filteredDocs = sampleDocuments.filter(
    (d) =>
      d.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      d.matter.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <AuthedShell wide>
      <div className="space-y-6">
        {/* Header Banner */}
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="font-sans text-xl font-semibold tracking-tight text-[#081534] md:text-2xl">
              Advocate Document Vault & Draft Store
            </h1>
            <p className="font-serif text-sm text-[#45464E]">
              Versioned contract drafts, Jinja2 skeleton docx outputs, and statutory filings.
            </p>
          </div>
          <a href="/contracts">
            <Button className="h-10 gap-2 rounded-sm bg-[#081534] font-sans text-xs font-semibold text-white transition-colors hover:bg-[#1E2A4A]">
              <Plus className="h-4 w-4" strokeWidth={1.5} />
              Generate New Draft
            </Button>
          </a>
        </div>

        {/* Document Search & Filter Card */}
        <Card className="rounded-sm border border-[#E4E2DD] bg-white p-4 shadow-none">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2">
              <FolderOpen className="h-4 w-4 text-[#081534]" strokeWidth={1.5} />
              <span className="font-sans text-xs font-semibold uppercase tracking-wider text-[#081534]">
                All Stored Legal Documents ({filteredDocs.length})
              </span>
            </div>
            <div className="relative w-full sm:w-64">
              <Search
                className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#76777F]"
                strokeWidth={1.5}
              />
              <Input
                type="text"
                placeholder="Search documents by title or matter..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-8 rounded-sm border-[#E4E2DD] bg-white pl-8 font-serif text-xs text-[#1A1A1A]"
              />
            </div>
          </div>
        </Card>

        {/* Document Cards List */}
        <div className="space-y-3">
          {filteredDocs.map((doc) => (
            <Card
              key={doc.id}
              className="rounded-sm border border-[#E4E2DD] bg-white p-4 shadow-none transition-colors hover:border-[#081534]"
            >
              <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] px-2 py-0.5 font-sans text-[10px] font-bold uppercase text-[#081534]">
                      {doc.category}
                    </span>
                    <span className="font-sans text-xs text-[#76777F]">{doc.updated_at}</span>
                  </div>
                  <h3 className="font-serif text-base font-medium text-[#1A1A1A]">
                    {doc.title}
                  </h3>
                  <p className="font-serif text-xs text-[#45464E]">
                    Matter: <span className="font-medium text-[#081534]">{doc.matter}</span> • Size: {doc.size}
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 gap-1.5 rounded-sm border-[#E4E2DD] font-sans text-xs font-medium text-[#081534] hover:bg-[#FBF9F4]"
                  >
                    <Download className="h-3.5 w-3.5" strokeWidth={1.5} />
                    Download DOCX
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </AuthedShell>
  );
}
