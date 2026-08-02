"use client";

import { ReactNode, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Session } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

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

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (!data.session) {
        router.push("/login");
      } else {
        setSession(data.session);
      }
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_event, s) => {
      if (!s) router.push("/login");
    });
    return () => sub.subscription.unsubscribe();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (session === "loading") {
    return <div className="p-8 text-sm text-muted-foreground">Loading…</div>;
  }

  return (
    <div className="min-h-screen bg-muted/30">
      <header className="flex items-center justify-between border-b bg-background px-6 py-3">
        <a href="/dashboard" className="font-semibold">
          VidhiDesk
        </a>
        <div className="flex items-center gap-4">
          <a href="/security" className="text-sm text-muted-foreground underline">
            Security
          </a>
          <Button
            variant="outline"
            size="sm"
            onClick={async () => {
              await supabase.auth.signOut();
              router.push("/login");
            }}
          >
            Sign out
          </Button>
        </div>
      </header>
      <div className="border-b bg-amber-50 px-6 py-2 text-center text-xs text-amber-900">
        AI-generated draft for advocate review. Not legal advice.
      </div>
      <main className={cn("mx-auto p-6", wide ? "max-w-6xl" : "max-w-3xl")}>{children}</main>
    </div>
  );
}
