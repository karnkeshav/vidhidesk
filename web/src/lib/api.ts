import { supabase } from "@/lib/supabase";

const API_URL = process.env.NEXT_PUBLIC_API_URL!;

export type Matter = {
  id: string;
  title: string;
  client_name: string | null;
  module: "litigation" | "contracts" | "rera" | "consulting";
  created_at: string;
};

export type Message = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  model_used: string | null;
  created_at: string;
};

async function authedFetch(path: string, init?: RequestInit) {
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) throw new Error("Not signed in");

  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.access_token}`,
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json();
}

export function listMatters(): Promise<Matter[]> {
  return authedFetch("/api/matters");
}

export function createMatter(input: {
  title: string;
  client_name?: string;
  module: Matter["module"];
}): Promise<Matter> {
  return authedFetch("/api/matters", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function listMessages(matterId: string): Promise<Message[]> {
  return authedFetch(`/api/matters/${matterId}/messages`);
}

export function sendMessage(
  matterId: string,
  content: string
): Promise<[Message, Message]> {
  return authedFetch(`/api/matters/${matterId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}
