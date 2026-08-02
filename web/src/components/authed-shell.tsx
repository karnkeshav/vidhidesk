"use client";

import { ReactNode, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Session } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ShieldCheck, Globe, LogOut } from "lucide-react";

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

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (!data.session) {
        router.push("/login");
      } else {
        setSession(data.session);
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
      <header className="sticky top-0 z-30 flex flex-wrap items-center justify-between gap-4 border-b border-[#E4E2DD] bg-white px-4 py-3 md:px-8">
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

        <div className="flex flex-wrap items-center gap-3 md:gap-4">
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

      <div className="border-b border-[#E4E2DD] bg-[#FFFBEB] px-4 py-2 text-center text-xs font-sans font-medium text-[#92400E]">
        AI-generated draft for advocate review. Not legal advice.
      </div>

      <main className={cn("mx-auto p-4 md:p-8", wide ? "max-w-7xl" : "max-w-6xl")}>
        {children}
      </main>
    </div>
  );
}
