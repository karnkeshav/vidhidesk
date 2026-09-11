"use client";

import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Session } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { listMatters, Matter, listCalendarHearings, CalendarHearing, startSession } from "@/lib/api";
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
  Building2,
} from "lucide-react";

// AuthedShell already needs the full matters list for its "Recent
// Matters" sidebar on every authed page. DashboardPage used to issue its
// own, separate listMatters() call for the same data (just unsliced) --
// two concurrent identical GETs on every dashboard load (Auth Request
// Forensics Sprint, item 8). Fetching once here and sharing it via
// context removes the duplicate without losing either the sidebar's
// top-4 view or the dashboard's own error banner.
type MattersContextValue = { matters: Matter[]; error: string | null };
const MattersContext = createContext<MattersContextValue>({ matters: [], error: null });
export function useMatters() {
  return useContext(MattersContext);
}

// Hearings are fetched once here (same "fetch once, share via context"
// reasoning as MattersContext above) so both the header bell and the
// /calendar page read the same list without issuing duplicate GETs.
type HearingsContextValue = { hearings: CalendarHearing[]; refetchHearings: () => void };
const HearingsContext = createContext<HearingsContextValue>({
  hearings: [],
  refetchHearings: () => {},
});
export function useHearings() {
  return useContext(HearingsContext);
}

const ONE_DAY_MS = 24 * 60 * 60 * 1000;
const NOTIFIED_HEARINGS_KEY_PREFIX = "vidhidesk_notified_hearings_";

/** Hearings landing strictly within the next 24h from `now`. */
function hearingsWithin24h(hearings: CalendarHearing[], now: Date): CalendarHearing[] {
  const cutoff = new Date(now.getTime() + ONE_DAY_MS);
  return hearings.filter((h) => {
    const t = new Date(h.hearing_at);
    return t > now && t <= cutoff;
  });
}

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
  const [matters, setMatters] = useState<Matter[]>([]);
  const [mattersError, setMattersError] = useState<string | null>(null);
  const [avatarUrl, setAvatarUrl] = useState<string>("");
  const [hearings, setHearings] = useState<CalendarHearing[]>([]);
  const [bellOpen, setBellOpen] = useState(false);
  const [notifPermission, setNotifPermission] = useState<NotificationPermission | "unsupported">(
    "unsupported"
  );

  const refetchHearings = () => {
    listCalendarHearings()
      .then(setHearings)
      .catch(() => {});
  };

  // Nav-visibility hint only, NOT security -- the real check is server-side
  // (api/app/auth.py::require_platform_owner). Showing/hiding this link
  // just avoids dangling a 403-only link in front of every signed-in user.
  const isPlatformOwner =
    session !== "loading" &&
    !!session?.user?.email &&
    session.user.email.trim().toLowerCase() ===
      (process.env.NEXT_PUBLIC_PLATFORM_OWNER_EMAIL || "").trim().toLowerCase();

  const loadAdvocateProfile = () => {
    supabase.auth.getUser().then(({ data }) => {
      if (data.user?.user_metadata?.avatar_url) {
        setAvatarUrl(data.user.user_metadata.avatar_url);
      } else {
        const saved = localStorage.getItem("vidhidesk_advocate_profile");
        if (saved) {
          try {
            const parsed = JSON.parse(saved);
            if (parsed.avatar_url) setAvatarUrl(parsed.avatar_url);
          } catch {}
        }
      }
    });
  };

  useEffect(() => {
    // TEMP DEBUG (Auth Request Forensics Sprint): confirms whether this
    // effect fires more than once per real mount (React StrictMode
    // double-invoke in dev) and whether the component unmounts while
    // listMatters() is still in flight. Remove once the sprint concludes.
    let unmounted = false;
    console.debug("[AuthedShell] effect mount");

    supabase.auth.getSession().then(({ data }) => {
      if (!data.session) {
        router.push("/login");
      } else {
        setSession(data.session);
        startSession().catch(() => {});
        listMatters()
          .then((data) => {
            if (unmounted) console.debug("[AuthedShell] listMatters resolved after unmount");
            setMatters(data);
          })
          .catch((err) => setMattersError(err instanceof Error ? err.message : String(err)));
        refetchHearings();
      }
    });

    if (typeof window !== "undefined" && "Notification" in window) {
      setNotifPermission(Notification.permission);
    }

    supabase.auth.getUser().then(({ data }) => {
      if (data.user?.user_metadata?.avatar_url) {
        setAvatarUrl(data.user.user_metadata.avatar_url);
      }
    });

    loadAdvocateProfile();

    const handleProfileUpdate = () => loadAdvocateProfile();
    window.addEventListener("advocate_profile_updated", handleProfileUpdate);

    const savedJurisdiction = localStorage.getItem("vidhidesk_jurisdiction");
    if (savedJurisdiction) {
      setJurisdiction(savedJurisdiction);
    }

    const { data: sub } = supabase.auth.onAuthStateChange((_event, s) => {
      if (!s) router.push("/login");
    });
    return () => {
      unmounted = true;
      console.debug("[AuthedShell] effect cleanup (unmount)");
      sub.subscription.unsubscribe();
      window.removeEventListener("advocate_profile_updated", handleProfileUpdate);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Browser "alarm" for the day-before hearing reminder: only fires once
  // notification permission has been explicitly granted (via the button
  // in the bell dropdown below -- requestPermission() needs a real user
  // gesture, calling it unprompted on load is unreliable/gets ignored by
  // browsers). Polls every 15 min while a tab stays open so it still
  // catches a hearing crossing the 24h mark mid-session, not just on
  // page load. De-dupes per calendar day via localStorage so the same
  // hearing doesn't re-fire an OS notification every poll.
  useEffect(() => {
    if (typeof window === "undefined" || !("Notification" in window)) return;

    const checkAndNotify = () => {
      if (Notification.permission !== "granted" || hearings.length === 0) return;
      const now = new Date();
      // Local calendar day, not UTC -- the dedupe window should reset at
      // the advocate's own midnight, not UTC midnight (see calendar
      // page.tsx's dateKey() for the same fix and why it matters).
      const pad = (n: number) => String(n).padStart(2, "0");
      const todayKey = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
      const storageKey = `${NOTIFIED_HEARINGS_KEY_PREFIX}${todayKey}`;
      let notified: string[] = [];
      try {
        notified = JSON.parse(localStorage.getItem(storageKey) || "[]");
      } catch {
        notified = [];
      }

      const due = hearingsWithin24h(hearings, now).filter((h) => !notified.includes(h.id));
      if (due.length === 0) return;

      due.forEach((h) => {
        const when = new Date(h.hearing_at).toLocaleString([], {
          weekday: "short",
          hour: "2-digit",
          minute: "2-digit",
        });
        new Notification("Hearing tomorrow", {
          body: `${h.title}${h.court ? ` — ${h.court}` : ""} — ${when}`,
          tag: h.id,
        });
      });

      try {
        localStorage.setItem(storageKey, JSON.stringify([...notified, ...due.map((h) => h.id)]));
      } catch {}
    };

    checkAndNotify();
    const interval = setInterval(checkAndNotify, 15 * 60 * 1000);
    return () => clearInterval(interval);
  }, [hearings]);

  const handleJurisdictionChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    setJurisdiction(val);
    localStorage.setItem("vidhidesk_jurisdiction", val);
  };

  const dueSoonHearings = hearingsWithin24h(hearings, new Date()).sort(
    (a, b) => new Date(a.hearing_at).getTime() - new Date(b.hearing_at).getTime()
  );

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
      <header className="sticky top-0 z-30 flex min-h-16 flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b border-[#E4E2DD] bg-white px-4 py-2 md:px-8">
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

          {/* Notifications Bell — hearings within the next 24h */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setBellOpen((v) => !v)}
              className="relative cursor-pointer text-[#45464E] transition-colors hover:text-[#081534]"
              title="Notifications"
              aria-label="Hearing notifications"
            >
              <Bell className="h-4 w-4" strokeWidth={1.5} />
              {dueSoonHearings.length > 0 && (
                <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-[#7A2A2A]"></span>
              )}
            </button>

            {bellOpen && (
              <>
                <div className="fixed inset-0 z-30" onClick={() => setBellOpen(false)} />
                <div className="absolute right-0 top-9 z-40 w-80 rounded-sm border border-[#E4E2DD] bg-white shadow-lg">
                  <div className="flex items-center justify-between border-b border-[#E4E2DD] px-3 py-2">
                    <span className="font-sans text-xs font-semibold uppercase tracking-wider text-[#081534]">
                      Hearings — Next 24 Hours
                    </span>
                  </div>

                  <div className="max-h-72 overflow-y-auto">
                    {dueSoonHearings.length === 0 ? (
                      <p className="px-3 py-4 font-serif text-xs text-[#76777F]">
                        No hearings in the next 24 hours.
                      </p>
                    ) : (
                      dueSoonHearings.map((h) => (
                        <a
                          key={h.id}
                          href="/calendar"
                          className="block border-b border-[#E4E2DD] px-3 py-2 last:border-b-0 hover:bg-[#FBF9F4]"
                        >
                          <p className="font-serif text-xs font-medium text-[#1A1A1A]">{h.title}</p>
                          <p className="font-sans text-[11px] text-[#45464E]">
                            {new Date(h.hearing_at).toLocaleString([], {
                              weekday: "short",
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                            {h.court ? ` · ${h.court}` : ""}
                          </p>
                        </a>
                      ))
                    )}
                  </div>

                  {notifPermission !== "unsupported" && notifPermission !== "granted" && (
                    <button
                      type="button"
                      onClick={() => {
                        Notification.requestPermission().then((perm) => setNotifPermission(perm));
                      }}
                      className="w-full border-t border-[#E4E2DD] px-3 py-2 text-left font-sans text-[11px] font-semibold text-[#081534] hover:bg-[#FBF9F4]"
                    >
                      Enable hearing alerts
                    </button>
                  )}
                  {notifPermission === "granted" && (
                    <p className="border-t border-[#E4E2DD] px-3 py-2 font-sans text-[11px] text-[#45464E]">
                      Hearing alerts enabled
                    </p>
                  )}
                </div>
              </>
            )}
          </div>

          {/* Settings Icon — Opens Profile & Credentials Page */}
          <a href="/profile" className="text-[#45464E] transition-colors hover:text-[#081534]" title="Advocate Settings & Credentials">
            <Settings className="h-4 w-4" strokeWidth={1.5} />
          </a>

          {/* User Profile Avatar Frame — Opens Profile & Photo Upload */}
          <a href="/profile" title="Edit Advocate Profile & Photo">
            <div className="flex h-8 w-8 items-center justify-center overflow-hidden rounded-sm border border-[#E4E2DD] bg-[#F0EEE9] text-[#081534] transition-all hover:border-[#081534]">
              {avatarUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={avatarUrl} alt="Advocate Profile" className="h-full w-full object-cover" />
              ) : (
                <User className="h-4 w-4" strokeWidth={1.5} />
              )}
            </div>
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

      {/* Advocate Review Banner */}
      <div className="border-b border-[#E4E2DD] bg-[#FFFBEB] px-4 py-2 text-center text-xs font-sans font-medium text-[#92400E]">
        AI-generated draft for advocate review. Not legal advice.
      </div>

      <div className="flex">
        {/* Left Sidebar Navigation (Exact Stitch Approved Design) */}
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
                href="/documents"
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
                <span>Research / Drafts</span>
              </a>
              <a
                href="/calendar"
                className="flex items-center gap-3 rounded-sm p-2.5 font-sans text-xs font-medium text-[#45464E] transition-colors hover:bg-[#E4E2DD] hover:text-[#081534]"
              >
                <Calendar className="h-4 w-4" strokeWidth={1.5} />
                <span>Calendar</span>
              </a>
              {isPlatformOwner && (
                <a
                  href="/platform"
                  className="flex items-center gap-3 rounded-sm p-2.5 font-sans text-xs font-medium text-[#45464E] transition-colors hover:bg-[#E4E2DD] hover:text-[#081534]"
                >
                  <Building2 className="h-4 w-4" strokeWidth={1.5} />
                  <span>Platform</span>
                </a>
              )}
            </nav>
          </div>

          {/* Bottom Left Navigation: Recent Matters Section */}
          <div className="border-t border-[#E4E2DD] pt-3">
            <p className="mb-2 px-2 font-sans text-[10px] font-bold uppercase tracking-widest text-[#45464E]">
              Recent Matters
            </p>
            <div className="space-y-1">
              {matters.length === 0 ? (
                <p className="px-2 font-serif text-xs text-[#76777F]">No recent matters</p>
              ) : (
                matters.slice(0, 4).map((m) => (
                  <a
                    key={m.id}
                    href={
                      m.module === "contracts"
                        ? `/contracts/${m.id}`
                        : m.module === "litigation"
                        ? `/litigation/${m.id}`
                        : `/matters/${m.id}`
                    }
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
          <MattersContext.Provider value={{ matters, error: mattersError }}>
            <HearingsContext.Provider value={{ hearings, refetchHearings }}>
              {children}
            </HearingsContext.Provider>
          </MattersContext.Provider>
        </main>
      </div>

      {/* Bottom Mobile Navigation Bar (Mobile Viewports Only - Stitch Approved Layout) */}
      <div className="fixed bottom-0 left-0 z-40 flex w-full items-center justify-around border-t border-[#E4E2DD] bg-white py-2 shadow-lg md:hidden">
        <a href="/dashboard" className="flex flex-col items-center gap-0.5 text-[#081534]">
          <LayoutDashboard className="h-4 w-4" strokeWidth={1.5} />
          <span className="font-sans text-[10px] font-semibold">Home</span>
        </a>
        <a href="/documents" className="flex flex-col items-center gap-0.5 text-[#45464E] transition-colors hover:text-[#081534]">
          <FolderKanban className="h-4 w-4" strokeWidth={1.5} />
          <span className="font-sans text-[10px] font-medium">Documents</span>
        </a>
        <a href="/admin/templates" className="flex flex-col items-center gap-0.5 text-[#45464E] transition-colors hover:text-[#081534]">
          <FileText className="h-4 w-4" strokeWidth={1.5} />
          <span className="font-sans text-[10px] font-medium">Research</span>
        </a>
        <a href="/calendar" className="flex flex-col items-center gap-0.5 text-[#45464E] transition-colors hover:text-[#081534]">
          <Calendar className="h-4 w-4" strokeWidth={1.5} />
          <span className="font-sans text-[10px] font-medium">Calendar</span>
        </a>
      </div>
    </div>
  );
}
