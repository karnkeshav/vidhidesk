"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Eye, EyeOff, ShieldCheck, AlertCircle } from "lucide-react";

type Step = "credentials" | "totp-verify";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"sign-in" | "sign-up">("sign-in");
  const [step, setStep] = useState<Step>("credentials");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
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
    <main className="flex min-h-screen flex-col items-center justify-center bg-[#FBF9F4] p-4 md:p-8 font-sans">
      <Card className="w-full max-w-md rounded-sm border border-[#E4E2DD] bg-white p-2 shadow-none sm:p-4">
        <CardHeader className="space-y-3 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-sm bg-[#081534] text-white">
              <ShieldCheck className="h-5 w-5" strokeWidth={1.5} />
            </div>
            <div>
              <CardTitle className="font-sans text-xl font-semibold tracking-tight text-[#081534] md:text-2xl">
                VidhiDesk
              </CardTitle>
              <span className="font-sans text-[11px] font-semibold uppercase tracking-wider text-[#45464E]">
                Legal AI Assistant
              </span>
            </div>
          </div>
          <CardDescription className="font-serif text-sm leading-relaxed text-[#45464E]">
            {step === "credentials" &&
              (mode === "sign-in"
                ? "Sign in to access your matters, litigation briefings, and verified statutory citations."
                : "Create an advocate workspace account.")}
            {step === "totp-verify" && "Enter your 6-digit authenticator security code."}
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-5">
          {step === "credentials" && (
            <form onSubmit={handleCredentialsSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <Label
                  htmlFor="email"
                  className="font-sans text-xs font-semibold uppercase tracking-wider text-[#1A1A1A]"
                >
                  Advocate Email
                </Label>
                <Input
                  id="email"
                  type="email"
                  required
                  placeholder="advocate@chamber.in"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="h-11 rounded-sm border-[#E4E2DD] bg-white font-serif text-sm text-[#1A1A1A] placeholder:text-[#9A9B9E] focus-visible:border-transparent focus-visible:ring-2 focus-visible:ring-[#081534]"
                />
              </div>

              <div className="space-y-1.5">
                <Label
                  htmlFor="password"
                  className="font-sans text-xs font-semibold uppercase tracking-wider text-[#1A1A1A]"
                >
                  Password
                </Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    required
                    minLength={6}
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="h-11 rounded-sm border-[#E4E2DD] bg-white pr-10 font-serif text-sm text-[#1A1A1A] placeholder:text-[#9A9B9E] focus-visible:border-transparent focus-visible:ring-2 focus-visible:ring-[#081534]"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[#45464E] hover:text-[#081534] focus:outline-none"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" strokeWidth={1.5} />
                    ) : (
                      <Eye className="h-4 w-4" strokeWidth={1.5} />
                    )}
                  </button>
                </div>
              </div>

              {error && (
                <div
                  role="alert"
                  className="flex items-center gap-2 rounded-sm border border-[#F8D7DA] bg-[#FFF5F5] p-3 text-xs font-sans text-[#7A2A2A]"
                >
                  <AlertCircle className="h-4 w-4 shrink-0 text-[#7A2A2A]" strokeWidth={1.5} />
                  <span>{error}</span>
                </div>
              )}

              <Button
                type="submit"
                disabled={busy}
                className="h-11 w-full rounded-sm bg-[#081534] font-sans text-sm font-medium text-white transition-colors hover:bg-[#1E2A4A] disabled:opacity-50"
              >
                {busy
                  ? mode === "sign-in"
                    ? "Signing in..."
                    : "Creating account..."
                  : mode === "sign-in"
                  ? "Sign in"
                  : "Create Account"}
              </Button>

              <button
                type="button"
                className="w-full text-center font-sans text-xs uppercase tracking-wider text-[#45464E] transition-colors hover:text-[#081534] hover:underline"
                onClick={() => setMode(mode === "sign-in" ? "sign-up" : "sign-in")}
              >
                {mode === "sign-in" ? "Need an account? Create one" : "Have an account? Sign in"}
              </button>
            </form>
          )}

          {step === "totp-verify" && (
            <form onSubmit={handleTotpVerify} className="space-y-4">
              <div className="space-y-1.5">
                <Label
                  htmlFor="totp"
                  className="font-sans text-xs font-semibold uppercase tracking-wider text-[#1A1A1A]"
                >
                  6-digit security code
                </Label>
                <Input
                  id="totp"
                  inputMode="numeric"
                  required
                  placeholder="123456"
                  value={totpCode}
                  onChange={(e) => setTotpCode(e.target.value)}
                  className="h-11 rounded-sm border-[#E4E2DD] bg-white font-serif text-sm tracking-widest text-[#1A1A1A] placeholder:text-[#9A9B9E] focus-visible:border-transparent focus-visible:ring-2 focus-visible:ring-[#081534]"
                />
              </div>

              {error && (
                <div
                  role="alert"
                  className="flex items-center gap-2 rounded-sm border border-[#F8D7DA] bg-[#FFF5F5] p-3 text-xs font-sans text-[#7A2A2A]"
                >
                  <AlertCircle className="h-4 w-4 shrink-0 text-[#7A2A2A]" strokeWidth={1.5} />
                  <span>{error}</span>
                </div>
              )}

              <Button
                type="submit"
                disabled={busy}
                className="h-11 w-full rounded-sm bg-[#081534] font-sans text-sm font-medium text-white transition-colors hover:bg-[#1E2A4A] disabled:opacity-50"
              >
                {busy ? "Verifying..." : "Verify Code"}
              </Button>
            </form>
          )}

          <div className="pt-2">
            <div className="border-t border-[#E4E2DD] pt-3 text-center">
              <p className="font-sans text-[11px] font-medium text-[#76777F]">
                AI-generated draft for advocate review. Not legal advice.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
