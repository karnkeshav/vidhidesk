"use client";

import { useEffect, useState } from "react";
import { AuthedShell } from "@/components/authed-shell";
import { supabase } from "@/lib/supabase";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

export default function SecurityPage() {
  const [verifiedFactorId, setVerifiedFactorId] = useState<string | null>(null);
  const [pendingFactorId, setPendingFactorId] = useState<string | null>(null);
  const [qrCode, setQrCode] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refreshFactors() {
    const { data } = await supabase.auth.mfa.listFactors();
    const verified = data?.totp?.find((f) => f.status === "verified");
    setVerifiedFactorId(verified?.id ?? null);
  }

  useEffect(() => {
    void refreshFactors();
  }, []);

  async function startEnroll() {
    setBusy(true);
    setError(null);
    try {
      const { data, error: enrollError } = await supabase.auth.mfa.enroll({
        factorType: "totp",
      });
      if (enrollError) throw enrollError;
      setPendingFactorId(data.id);
      setQrCode(data.totp.qr_code);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function confirmEnroll(e: React.FormEvent) {
    e.preventDefault();
    if (!pendingFactorId) return;
    setBusy(true);
    setError(null);
    try {
      const { data: challenge, error: challengeError } = await supabase.auth.mfa.challenge({
        factorId: pendingFactorId,
      });
      if (challengeError) throw challengeError;
      const { error: verifyError } = await supabase.auth.mfa.verify({
        factorId: pendingFactorId,
        challengeId: challenge.id,
        code,
      });
      if (verifyError) throw verifyError;
      setPendingFactorId(null);
      setQrCode(null);
      setCode("");
      setNotice("Two-factor authentication enabled.");
      await refreshFactors();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function disableFactor() {
    if (!verifiedFactorId) return;
    setBusy(true);
    setError(null);
    try {
      const { error: unenrollError } = await supabase.auth.mfa.unenroll({
        factorId: verifiedFactorId,
      });
      if (unenrollError) throw unenrollError;
      setVerifiedFactorId(null);
      setNotice("Two-factor authentication disabled.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthedShell>
      <Card>
        <CardHeader>
          <CardTitle>Two-factor authentication</CardTitle>
          <CardDescription>
            TOTP via an authenticator app (Google Authenticator, 1Password, etc.).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {notice && <p className="text-sm text-emerald-700">{notice}</p>}
          {error && <p className="text-sm text-destructive">{error}</p>}

          {verifiedFactorId && !pendingFactorId && (
            <div className="space-y-3">
              <p className="text-sm">Two-factor authentication is enabled.</p>
              <Button variant="outline" onClick={disableFactor} disabled={busy}>
                Disable
              </Button>
            </div>
          )}

          {!verifiedFactorId && !pendingFactorId && (
            <Button onClick={startEnroll} disabled={busy}>
              Enable two-factor authentication
            </Button>
          )}

          {pendingFactorId && qrCode && (
            <form onSubmit={confirmEnroll} className="space-y-4">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={qrCode} alt="TOTP QR code" className="h-40 w-40" />
              <div className="space-y-2">
                <Label htmlFor="code">Code from your authenticator app</Label>
                <Input
                  id="code"
                  inputMode="numeric"
                  required
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                />
              </div>
              <Button type="submit" disabled={busy}>
                Confirm
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </AuthedShell>
  );
}
