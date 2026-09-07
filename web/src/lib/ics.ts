// Minimal RFC 5545 (.ics) generator for a single hearing -- fully
// client-side, deterministic, no provider/API dependency, so unlike the
// advocate/IA data this is real functionality, not a placeholder. Only
// the handful of properties every calendar client (Google Calendar,
// Outlook, Apple Calendar) actually needs to import a one-off event.

function icsEscape(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\n/g, "\\n");
}

function toIcsUtc(iso: string): string {
  const d = new Date(iso);
  return d.toISOString().replace(/[-:]/g, "").split(".")[0] + "Z";
}

export function buildHearingIcs(input: {
  uid: string;
  title: string;
  hearingAt: string; // ISO datetime
  durationMinutes?: number;
  location?: string | null;
  description?: string | null;
}): string {
  const start = new Date(input.hearingAt);
  const end = new Date(start.getTime() + (input.durationMinutes ?? 60) * 60000);
  const now = toIcsUtc(new Date().toISOString());

  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//VidhiDesk//Hearing Calendar//EN",
    "CALSCALE:GREGORIAN",
    "BEGIN:VEVENT",
    `UID:${icsEscape(input.uid)}@vidhidesk`,
    `DTSTAMP:${now}`,
    `DTSTART:${toIcsUtc(start.toISOString())}`,
    `DTEND:${toIcsUtc(end.toISOString())}`,
    `SUMMARY:${icsEscape(input.title)}`,
  ];
  if (input.location) lines.push(`LOCATION:${icsEscape(input.location)}`);
  if (input.description) lines.push(`DESCRIPTION:${icsEscape(input.description)}`);
  lines.push("END:VEVENT", "END:VCALENDAR");
  return lines.join("\r\n");
}

export function downloadIcs(filename: string, icsContent: string) {
  const blob = new Blob([icsContent], { type: "text/calendar;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
