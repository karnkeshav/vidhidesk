"use client";

import { useState } from "react";
import { supabase } from "@/lib/supabase";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { ShieldCheck, Clock, LogOut } from "lucide-react";

// Landed on by lib/api.ts's authedFetch whenever the backend returns
// 401 TRIAL_EXPIRED (app/auth.py::_check_account_not_locked). Deliberately
// does not sign the user out -- their Supabase session stays valid, and
// the moment Nitesh flips payment_received to true in the Supabase Table
// Editor, the "Check again" button below (or any normal navigation) will
// succeed without a fresh login.
export default function TrialExpiredPage() {
  const [checking, setChecking] = useState(false);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-[#FBF9F4] p-4 md:p-8 font-sans">
      <Card className="w-full max-w-md rounded-sm border border-[#E4E2DD] bg-white p-2 shadow-none sm:p-4">
        <CardHeader className="space-y-3 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-sm bg-[#081534] text-white">
              <Clock className="h-5 w-5" strokeWidth={1.5} />
            </div>
            <div>
              <CardTitle className="font-sans text-xl font-semibold tracking-tight text-[#081534] md:text-2xl">
                Free trial ended
              </CardTitle>
              <span className="font-sans text-[11px] font-semibold uppercase tracking-wider text-[#45464E]">
                VidhiDesk
              </span>
            </div>
          </div>
          <CardDescription className="font-serif text-sm leading-relaxed text-[#45464E]">
            Your 5-day free exploration period has ended. To keep using VidhiDesk, please
            arrange payment with your point of contact. Access resumes automatically as soon
            as payment is confirmed on our end — you will not need to sign in again.
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="flex items-center gap-2 rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] p-3 text-xs font-sans text-[#45464E]">
            <ShieldCheck className="h-4 w-4 shrink-0 text-[#081534]" strokeWidth={1.5} />
            <span>Your account and data are untouched and waiting for you.</span>
          </div>

          <Button
            type="button"
            disabled={checking}
            onClick={() => {
              setChecking(true);
              // A full reload re-runs every authed page's data fetch, so
              // this both re-checks payment_received and, if it has been
              // flipped, lands the advocate straight back in the app.
              window.location.href = "/dashboard";
            }}
            className="h-11 w-full rounded-sm bg-[#081534] font-sans text-sm font-medium text-white transition-colors hover:bg-[#1E2A4A] disabled:opacity-50"
          >
            {checking ? "Checking..." : "Check again"}
          </Button>

          <button
            type="button"
            onClick={async () => {
              await supabase.auth.signOut();
              window.location.href = "/login";
            }}
            className="flex w-full items-center justify-center gap-1.5 text-center font-sans text-xs uppercase tracking-wider text-[#45464E] transition-colors hover:text-[#081534] hover:underline"
          >
            <LogOut className="h-3.5 w-3.5" strokeWidth={1.5} />
            Sign out
          </button>

          <div className="border-t border-[#E4E2DD] pt-3 text-center">
            <p className="font-sans text-[11px] font-medium text-[#76777F]">
              AI-generated draft for advocate review. Not legal advice.
            </p>
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
