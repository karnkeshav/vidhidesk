"use client";

import { ReactNode, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Session } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { listMatters, Matter } from "@/lib/api";
import {
  ShieldCheck,
  Globe,
  LogOut,
  LayoutDashboard,
  FolderKanban,
  FileText,
  Calendar,
  Plus,
  Gavel,
  Bell,
  Settings,
  User,
} from "lucide-react";

export function AuthedShell({
  children,
  wide = false,
}: {
  children: ReactNode;
  /** Wider content column for two-panel layouts (e.g. clause review). */
  wide?: boolean;
}) {
  const router = useRouter();
  const [session, setSession] = useState<Session | null | "loading">("loading");
  const [jurisdiction, setJurisdiction] = useState<string>("Delhi");
  const [recentMatters, setRecentMatters] = useState<Matter[]>([]);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (!data.session) {
        router.push("/login");
      } else {
        setSession(data.session);
        listMatters()
          .then((data) => setRecentMatters(data.slice(0, 4)))
          .catch(() => {});
      }
    });

    const savedJurisdiction = localStorage.getItem("vidhidesk_jurisdiction");
    if (savedJurisdiction) {
      setJurisdiction(savedJurisdiction);
    }

    const { data: sub } = supabase.auth.onAuthStateChange((_event, s) => {
      if (!s) router.push("/login");
    });
    return () => sub.subscription.unsubscribe();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleJurisdictionChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    setJurisdiction(val);
    localStorage.setItem("vidhidesk_jurisdiction", val);
  };

  if (session === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#FBF9F4] font-sans text-sm text-[#45464E]">
        Loading advocate workspace…
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#FBF9F4] font-sans text-[#1A1A1A]">
      {/* Top Header Navigation Bar */}
      <header className="sticky top-0 z-30 flex h-16 flex-wrap items-center justify-between gap-4 border-b border-[#E4E2DD] bg-white px-4 md:px-8">
        <div className="flex items-center gap-3">
          <a href="/dashboard" className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-sm bg-[#081534] text-white">
              <ShieldCheck className="h-4 w-4" strokeWidth={1.5} />
            </div>
            <span className="font-sans text-lg font-semibold tracking-tight text-[#081534]">
              VidhiDesk
            </span>
          </a>
          <span className="hidden rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] px-2 py-0.5 font-sans text-[11px] font-semibold uppercase tracking-wider text-[#45464E] sm:inline-block">
            Legal AI Assistant
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-3 md:gap-5">
          <div className="flex items-center gap-1.5 rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] px-2.5 py-1">
            <Globe className="h-3.5 w-3.5 text-[#45464E]" strokeWidth={1.5} />
            <span className="font-sans text-xs font-medium text-[#45464E]">State:</span>
            <select
              value={jurisdiction}
              onChange={handleJurisdictionChange}
              className="bg-transparent font-sans text-xs font-semibold text-[#081534] focus:outline-none"
              aria-label="Select Legal Jurisdiction State"
            >
              <option value="Delhi">Delhi</option>
              <option value="Maharashtra">Maharashtra</option>
              <option value="UP">Uttar Pradesh (UP)</option>
            </select>
          </div>

          <a
            href="/admin/templates"
            className="font-sans text-xs font-medium uppercase tracking-wider text-[#45464E] transition-colors hover:text-[#081534] hover:underline"
          >
            Templates
          </a>

          <a
            href="/security"
            className="font-sans text-xs font-medium uppercase tracking-wider text-[#45464E] transition-colors hover:text-[#081534] hover:underline"
          >
            Security
          </a>

          {/* Notifications Icon with Badge (Stitch Approved Design) */}
          <div className="relative cursor-pointer text-[#45464E] transition-colors hover:text-[#081534]" title="Notifications">
            <Bell className="h-4 w-4" strokeWidth={1.5} />
            <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-[#7A2A2A]"></span>
          </div>

          {/* Settings Icon */}
          <a href="/security" className="text-[#45464E] transition-colors hover:text-[#081534]" title="Settings">
            <Settings className="h-4 w-4" strokeWidth={1.5} />
          </a>

          {/* User Profile Avatar Frame */}
          <div className="flex h-8 w-8 items-center justify-center rounded-sm border border-[#E4E2DD] bg-[#F0EEE9] text-[#081534]" title="Advocate Profile">
            <User className="h-4 w-4" strokeWidth={1.5} />
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={async () => {
              await supabase.auth.signOut();
              router.push("/login");
            }}
            className="h-8 gap-1.5 rounded-sm border-[#E4E2DD] font-sans text-xs font-medium text-[#081534] hover:bg-[#FBF9F4]"
          >
            <LogOut className="h-3.5 w-3.5" strokeWidth={1.5} />
            Sign out
          </Button>
        </div>
      </header>

      {/* Advocate Review Banner */}
      <div className="border-b border-[#E4E2DD] bg-[#FFFBEB] px-4 py-2 text-center text-xs font-sans font-medium text-[#92400E]">
        AI-generated draft for advocate review. Not legal advice.
      </div>

      <div className="flex">
        {/* Left Sidebar Navigation (Desktop Viewports) */}
        <aside className="sticky top-16 hidden h-[calc(100vh-64px)] w-64 shrink-0 flex-col justify-between gap-4 border-r border-[#E4E2DD] bg-[#F0EEE9] p-4 md:flex">
          <div className="space-y-4">
            <a href="/contracts">
              <Button className="flex w-full items-center justify-center gap-2 rounded-sm bg-[#081534] py-2.5 font-sans text-xs font-semibold uppercase tracking-wider text-white transition-colors hover:bg-[#1E2A4A]">
                <Plus className="h-4 w-4" strokeWidth={1.5} />
                New Matter
              </Button>
            </a>

            <nav className="flex flex-col gap-1">
              <a
                href="/dashboard"
                className="flex items-center gap-3 rounded-sm bg-[#1E2A4A] p-2.5 font-sans text-xs font-semibold text-white"
              >
                <LayoutDashboard className="h-4 w-4" strokeWidth={1.5} />
                <span>Dashboard</span>
              </a>
              <a
                href="/contracts"
                className="flex items-center gap-3 rounded-sm p-2.5 font-sans text-xs font-medium text-[#45464E] transition-colors hover:bg-[#E4E2DD] hover:text-[#081534]"
              >
                <Gavel className="h-4 w-4" strokeWidth={1.5} />
                <span>Matter List</span>
              </a>
              <a
                href="/contracts"
                className="flex items-center gap-3 rounded-sm p-2.5 font-sans text-xs font-medium text-[#45464E] transition-colors hover:bg-[#E4E2DD] hover:text-[#081534]"
              >
                <FolderKanban className="h-4 w-4" strokeWidth={1.5} />
                <span>Documents</span>
              </a>
              <a
                href="/admin/templates"
                className="flex items-center gap-3 rounded-sm p-2.5 font-sans text-xs font-medium text-[#45464E] transition-colors hover:bg-[#E4E2DD] hover:text-[#081534]"
              >
                <FileText className="h-4 w-4" strokeWidth={1.5} />
                <span>Research</span>
              </a>
              <a
                href="/dashboard"
                className="flex items-center gap-3 rounded-sm p-2.5 font-sans text-xs font-medium text-[#45464E] transition-colors hover:bg-[#E4E2DD] hover:text-[#081534]"
              >
                <Calendar className="h-4 w-4" strokeWidth={1.5} />
                <span>Calendar</span>
              </a>
            </nav>
          </div>

          {/* Bottom Left Navigation: Recent Matters Section */}
          <div className="border-t border-[#E4E2DD] pt-3">
            <p className="mb-2 px-2 font-sans text-[10px] font-bold uppercase tracking-widest text-[#45464E]">
              Recent Matters
            </p>
            <div className="space-y-1">
              {recentMatters.length === 0 ? (
                <p className="px-2 font-serif text-xs text-[#76777F]">No recent matters</p>
              ) : (
                recentMatters.map((m) => (
                  <a
                    key={m.id}
                    href={m.module === "contracts" ? `/contracts/${m.id}` : `/matters/${m.id}`}
                    className="block truncate rounded-sm px-2 py-1.5 font-serif text-xs font-medium text-[#081534] transition-colors hover:bg-[#E4E2DD]"
                  >
                    {m.title}
                  </a>
                ))
              )}
            </div>
          </div>
        </aside>

        {/* Main Workspace Canvas */}
        <main className={cn("w-full min-w-0 p-4 pb-20 md:p-6 md:pb-6", wide ? "max-w-7xl" : "max-w-6xl")}>
          {children}
        </main>
      </div>

      {/* Bottom Mobile Navigation Bar (Mobile Viewports Only - Stitch Approved Layout) */}
      <div className="fixed bottom-0 left-0 z-40 flex w-full items-center justify-around border-t border-[#E4E2DD] bg-white py-2 shadow-lg md:hidden">
        <a href="/dashboard" className="flex flex-col items-center gap-0.5 text-[#081534]">
          <LayoutDashboard className="h-4 w-4" strokeWidth={1.5} />
          <span className="font-sans text-[10px] font-semibold">Home</span>
        </a>
        <a href="/contracts" className="flex flex-col items-center gap-0.5 text-[#45464E] transition-colors hover:text-[#081534]">
          <FolderKanban className="h-4 w-4" strokeWidth={1.5} />
          <span className="font-sans text-[10px] font-medium">Matters</span>
        </a>
        <a href="/admin/templates" className="flex flex-col items-center gap-0.5 text-[#45464E] transition-colors hover:text-[#081534]">
          <FileText className="h-4 w-4" strokeWidth={1.5} />
          <span className="font-sans text-[10px] font-medium">Research</span>
        </a>
        <a href="/security" className="flex flex-col items-center gap-0.5 text-[#45464E] transition-colors hover:text-[#081534]">
          <ShieldCheck className="h-4 w-4" strokeWidth={1.5} />
          <span className="font-sans text-[10px] font-medium">Security</span>
        </a>
      </div>
    </div>
  );
}
