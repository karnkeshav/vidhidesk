"use client";

import { useState } from "react";
import { AuthedShell } from "@/components/authed-shell";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Calendar as CalendarIcon, Gavel, Plus, Clock, MapPin, Search } from "lucide-react";
import { Input } from "@/components/ui/input";

export default function CalendarPage() {
  const [selectedDate] = useState("Today, 2 Aug 2026");
  const [searchQuery, setSearchQuery] = useState("");

  const hearings = [
    {
      id: "1",
      case_no: "Civil Suit 1042/2026",
      title: "Acme Corp vs. Union of India",
      court: "Delhi High Court — Court Room 4",
      bench: "Hon'ble Mr. Justice R.K. Malhotra",
      item_no: "Item 14",
      stage: "Final Arguments",
      time: "10:30 AM",
    },
    {
      id: "2",
      case_no: "RERA Comp #402/2025",
      title: "Urban Infra Phase II Registration Audit",
      court: "Maharashtra RERA Tribunal — Chamber 2",
      bench: "Adjudicating Officer S. Varma",
      item_no: "Item 08",
      stage: "Compliance Hearing",
      time: "02:15 PM",
    },
  ];

  const filteredHearings = hearings.filter(
    (h) =>
      h.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      h.case_no.toLowerCase().includes(searchQuery.toLowerCase()) ||
      h.court.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <AuthedShell wide>
      <div className="space-y-6">
        {/* Page Title Banner */}
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="font-sans text-xl font-semibold tracking-tight text-[#081534] md:text-2xl">
              Advocate Cause List & Calendar
            </h1>
            <p className="font-serif text-sm text-[#45464E]">
              Track court room dockets, hearing dates, and statutory filing deadlines.
            </p>
          </div>
          <Button className="h-10 gap-2 rounded-sm bg-[#081534] font-sans text-xs font-semibold text-white transition-colors hover:bg-[#1E2A4A]">
            <Plus className="h-4 w-4" strokeWidth={1.5} />
            Schedule Hearing Date
          </Button>
        </div>

        {/* Cause List Calendar & Schedule Layout */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* Main Hearing Dockets Table (8 Columns) */}
          <div className="space-y-4 lg:col-span-8">
            <Card className="rounded-sm border border-[#E4E2DD] bg-white p-4 shadow-none">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-2">
                  <Gavel className="h-4 w-4 text-[#081534]" strokeWidth={1.5} />
                  <span className="font-sans text-xs font-semibold uppercase tracking-wider text-[#081534]">
                    Listed Court Appearances ({selectedDate})
                  </span>
                </div>
                <div className="relative w-full sm:w-60">
                  <Search
                    className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#76777F]"
                    strokeWidth={1.5}
                  />
                  <Input
                    type="text"
                    placeholder="Search hearings or cases..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="h-8 rounded-sm border-[#E4E2DD] bg-white pl-8 font-serif text-xs text-[#1A1A1A]"
                  />
                </div>
              </div>
            </Card>

            <div className="space-y-3">
              {filteredHearings.map((h) => (
                <Card
                  key={h.id}
                  className="rounded-sm border border-[#E4E2DD] bg-white p-4 shadow-none transition-all hover:border-[#081534]"
                >
                  <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] px-2 py-0.5 font-sans text-[10px] font-bold uppercase text-[#081534]">
                          {h.case_no}
                        </span>
                        <span className="rounded-sm bg-[#1E2A4A] px-2 py-0.5 font-sans text-[10px] font-semibold text-white">
                          {h.item_no}
                        </span>
                      </div>
                      <h3 className="font-serif text-base font-medium text-[#1A1A1A]">
                        {h.title}
                      </h3>
                      <div className="flex items-center gap-1.5 font-sans text-xs text-[#45464E]">
                        <MapPin className="h-3.5 w-3.5 text-[#76777F]" />
                        <span>{h.court}</span>
                      </div>
                      <p className="font-serif text-xs italic text-[#76777F]">
                        Bench: {h.bench}
                      </p>
                    </div>

                    <div className="flex flex-col items-start gap-2 sm:items-end">
                      <div className="flex items-center gap-1 font-sans text-xs font-semibold text-[#7A2A2A]">
                        <Clock className="h-3.5 w-3.5" />
                        <span>{h.time}</span>
                      </div>
                      <span className="rounded-sm border border-[#E4E2DD] bg-[#F6F3EE] px-2 py-1 font-sans text-[11px] font-medium text-[#081534]">
                        Stage: {h.stage}
                      </span>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </div>

          {/* Right Sidebar Calendar Controls (4 Columns) */}
          <div className="space-y-4 lg:col-span-4">
            <Card className="rounded-sm border border-[#E4E2DD] bg-white shadow-none">
              <CardHeader className="border-b border-[#E4E2DD] p-4">
                <div className="flex items-center gap-2">
                  <CalendarIcon className="h-4 w-4 text-[#081534]" strokeWidth={1.5} />
                  <CardTitle className="font-sans text-xs font-semibold uppercase tracking-wider text-[#081534]">
                    Calendar Month Overview
                  </CardTitle>
                </div>
                <CardDescription className="font-serif text-xs text-[#45464E]">
                  August 2026
                </CardDescription>
              </CardHeader>
              <CardContent className="p-4">
                <div className="rounded-sm border border-dashed border-[#E4E2DD] bg-[#FBF9F4] p-4 text-center">
                  <p className="font-sans text-xs font-semibold text-[#1A1A1A]">
                    2 Listed Appearances Today
                  </p>
                  <p className="mt-1 font-serif text-[11px] text-[#76777F]">
                    Click any hearing docket to view case history or evidentiary logs.
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </AuthedShell>
  );
}
