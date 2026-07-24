"use client";

import { useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { AuthedShell } from "@/components/authed-shell";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { listMessages, sendMessage, Message } from "@/lib/api";
import { cn } from "@/lib/utils";

export default function MatterChatPage() {
  const params = useParams<{ id: string }>();
  const matterId = params.id;
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  async function refresh() {
    try {
      setMessages(await listMessages(matterId));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matterId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!draft.trim()) return;
    setBusy(true);
    setError(null);
    const content = draft;
    setDraft("");
    try {
      const [userMsg, assistantMsg] = await sendMessage(matterId, content);
      setMessages((prev) => [...prev, userMsg, assistantMsg]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setDraft(content);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthedShell>
      <div className="flex h-[75vh] flex-col">
        <div className="flex-1 space-y-3 overflow-y-auto rounded-md border bg-background p-4">
          {messages.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No messages yet — send one below. It round-trips through the
              masked LLM gateway and is stored here.
            </p>
          )}
          {messages.map((m) => (
            <div
              key={m.id}
              className={cn(
                "max-w-[80%] rounded-lg px-3 py-2 text-sm",
                m.role === "user"
                  ? "ml-auto bg-primary text-primary-foreground"
                  : "bg-muted"
              )}
            >
              <div>{m.content}</div>
              {m.model_used && (
                <div className="mt-1 text-[10px] opacity-70">via {m.model_used}</div>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
        <form onSubmit={handleSend} className="mt-3 flex gap-2">
          <Textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Type a fact pattern or question…"
            className="flex-1"
            rows={2}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void handleSend(e);
              }
            }}
          />
          <Button type="submit" disabled={busy}>
            Send
          </Button>
        </form>
        {error && <p className="mt-2 text-sm text-destructive">{error}</p>}
      </div>
    </AuthedShell>
  );
}
