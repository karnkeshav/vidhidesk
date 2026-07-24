"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

type Step = "credentials" | "totp-verify";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"sign-in" | "sign-up">("sign-in");
  const [step, setStep] = useState<Step>("credentials");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [factorId, setFactorId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) void afterSignIn();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function afterSignIn() {
    const { data: aal } = await supabase.auth.mfa.getAuthenticatorAssuranceLevel();
    if (aal && aal.nextLevel === "aal2" && aal.currentLevel !== aal.nextLevel) {
      const { data: factors } = await supabase.auth.mfa.listFactors();
      const totp = factors?.totp?.find((f) => f.status === "verified");
      if (totp) {
        setFactorId(totp.id);
        setStep("totp-verify");
        return;
      }
    }
    router.push("/dashboard");
  }

  async function handleCredentialsSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "sign-up") {
        const { error: signUpError } = await supabase.auth.signUp({ email, password });
        if (signUpError) throw signUpError;
        setError("Check your inbox to confirm the address, then sign in.");
        setMode("sign-in");
      } else {
        const { error: signInError } = await supabase.auth.signInWithPassword({
          email,
          password,
        });
        if (signInError) throw signInError;
        await afterSignIn();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleTotpVerify(e: React.FormEvent) {
    e.preventDefault();
    if (!factorId) return;
    setBusy(true);
    setError(null);
    try {
      const { data: challenge, error: challengeError } =
        await supabase.auth.mfa.challenge({ factorId });
      if (challengeError) throw challengeError;
      const { error: verifyError } = await supabase.auth.mfa.verify({
        factorId,
        challengeId: challenge.id,
        code: totpCode,
      });
      if (verifyError) throw verifyError;
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>VidhiDesk</CardTitle>
          <CardDescription>
            {step === "credentials" &&
              (mode === "sign-in" ? "Sign in to your matters." : "Create your account.")}
            {step === "totp-verify" && "Enter your authenticator code."}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {step === "credentials" && (
            <form onSubmit={handleCredentialsSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  required
                  minLength={6}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
              {error && <p className="text-sm text-destructive">{error}</p>}
              <Button type="submit" className="w-full" disabled={busy}>
                {mode === "sign-in" ? "Sign in" : "Sign up"}
              </Button>
              <button
                type="button"
                className="w-full text-center text-sm text-muted-foreground underline"
                onClick={() => setMode(mode === "sign-in" ? "sign-up" : "sign-in")}
              >
                {mode === "sign-in" ? "Need an account? Sign up" : "Have an account? Sign in"}
              </button>
            </form>
          )}

          {step === "totp-verify" && (
            <form onSubmit={handleTotpVerify} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="totp">6-digit code</Label>
                <Input
                  id="totp"
                  inputMode="numeric"
                  required
                  value={totpCode}
                  onChange={(e) => setTotpCode(e.target.value)}
                />
              </div>
              {error && <p className="text-sm text-destructive">{error}</p>}
              <Button type="submit" className="w-full" disabled={busy}>
                Verify
              </Button>
            </form>
          )}

        </CardContent>
      </Card>
    </main>
  );
}
