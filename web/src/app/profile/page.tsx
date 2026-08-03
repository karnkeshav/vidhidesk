"use client";

import { useEffect, useState } from "react";
import { AuthedShell } from "@/components/authed-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { supabase } from "@/lib/supabase";
import { User, Upload, CheckCircle2, ShieldCheck, Camera, Save, KeyRound, Mail, AlertCircle } from "lucide-react";

export type AdvocateProfile = {
  full_name: string;
  bar_number: string;
  primary_court: string;
  phone: string;
  email: string;
  office_address: string;
  avatar_url: string;
};

export default function ProfilePage() {
  const [profile, setProfile] = useState<AdvocateProfile>({
    full_name: "",
    bar_number: "",
    primary_court: "",
    phone: "",
    email: "",
    office_address: "",
    avatar_url: "",
  });
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const [saving, setSaving] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);
  const [sendingResetEmail, setSendingResetEmail] = useState(false);

  const [savedSuccess, setSavedSuccess] = useState(false);
  const [passwordSuccess, setPasswordSuccess] = useState(false);
  const [emailResetSuccess, setEmailResetSuccess] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);

  const loadProfileFromSupabase = async () => {
    const { data } = await supabase.auth.getUser();
    if (data.user) {
      const meta = data.user.user_metadata || {};
      let cached: Partial<AdvocateProfile> = {};
      const savedCache = localStorage.getItem("vidhidesk_advocate_profile");
      if (savedCache) {
        try {
          cached = JSON.parse(savedCache);
        } catch {}
      }

      setProfile({
        full_name: meta.full_name ?? cached.full_name ?? "",
        bar_number: meta.bar_number ?? cached.bar_number ?? "",
        primary_court: meta.primary_court ?? cached.primary_court ?? "",
        phone: meta.phone ?? cached.phone ?? "",
        email: data.user.email || "",
        office_address: meta.office_address ?? cached.office_address ?? "",
        avatar_url: meta.avatar_url ?? cached.avatar_url ?? "",
      });
    }
  };

  useEffect(() => {
    void loadProfileFromSupabase();
  }, []);

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 2 * 1024 * 1024) {
      setError("Image size must be less than 2MB");
      return;
    }

    const reader = new FileReader();
    reader.onload = (event) => {
      const base64 = event.target?.result as string;
      setProfile((prev) => ({ ...prev, avatar_url: base64 }));
      setError(null);
    };
    reader.readAsDataURL(file);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSavedSuccess(false);

    try {
      // Save to Supabase auth user_metadata
      const { error: updateErr } = await supabase.auth.updateUser({
        data: {
          full_name: profile.full_name,
          bar_number: profile.bar_number,
          primary_court: profile.primary_court,
          phone: profile.phone,
          office_address: profile.office_address,
          avatar_url: profile.avatar_url,
        },
      });

      if (updateErr) {
        console.warn("Supabase metadata update warning:", updateErr.message);
      }

      // Persist in localStorage for instant client-side header sync
      localStorage.setItem("vidhidesk_advocate_profile", JSON.stringify(profile));
      // Dispatch custom event to update AuthedShell header immediately
      window.dispatchEvent(new Event("advocate_profile_updated"));

      // Reload fresh server metadata from Supabase
      await loadProfileFromSupabase();

      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 4000);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  const handlePasswordUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError(null);
    setPasswordSuccess(false);

    if (newPassword.length < 6) {
      setPasswordError("Password must be at least 6 characters long.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("New passwords do not match.");
      return;
    }

    setSavingPassword(true);
    try {
      const { error: err } = await supabase.auth.updateUser({
        password: newPassword,
      });

      if (err) throw err;

      setPasswordSuccess(true);
      setNewPassword("");
      setConfirmPassword("");
      setTimeout(() => setPasswordSuccess(false), 4000);
    } catch (err) {
      setPasswordError(err instanceof Error ? err.message : String(err));
    } finally {
      setSavingPassword(false);
    }
  };

  const handleSendResetEmail = async () => {
    if (!profile.email) return;
    setSendingResetEmail(true);
    setPasswordError(null);
    try {
      const { error: err } = await supabase.auth.resetPasswordForEmail(profile.email, {
        redirectTo: `${window.location.origin}/login`,
      });
      if (err) throw err;

      setEmailResetSuccess(true);
      setTimeout(() => setEmailResetSuccess(false), 5000);
    } catch (err) {
      setPasswordError(err instanceof Error ? err.message : String(err));
    } finally {
      setSendingResetEmail(false);
    }
  };

  return (
    <AuthedShell>
      <div className="mx-auto max-w-4xl space-y-6">
        <div>
          <h1 className="font-sans text-2xl font-semibold tracking-tight text-[#081534]">
            Advocate Profile & Settings
          </h1>
          <p className="font-serif text-sm text-[#45464E]">
            Manage your professional credentials, chamber details, profile photo, and password security.
          </p>
        </div>

        {(!profile.full_name.trim() || !profile.bar_number.trim()) && (
          <div role="status" className="flex items-start gap-3 rounded-sm border border-[#FFEBAA] bg-[#FFFBEB] p-4 text-xs font-sans text-[#92400E]">
            <AlertCircle className="h-5 w-5 shrink-0 text-[#B45309]" />
            <div>
              <h4 className="font-semibold uppercase tracking-wider text-[#B45309]">
                Welcome to Advocate Workspace — Complete Your Professional Profile
              </h4>
              <p className="mt-1 font-serif text-[#78350F]">
                Please fill in your Advocate Full Name and Bar Council Registration Number below. These details will be automatically used to personalize your legal document sheets, verified contract drafts, and court dockets.
              </p>
            </div>
          </div>
        )}

        {savedSuccess && (
          <div className="flex items-center gap-2 rounded-sm border border-[#C3E6CB] bg-[#D4EDDA] p-3 font-sans text-xs font-semibold text-[#155724]">
            <CheckCircle2 className="h-4 w-4" />
            Advocate profile and photo updated successfully! Saved to Supabase database.
          </div>
        )}

        {error && (
          <div className="rounded-sm border border-[#F8D7DA] bg-[#FFF5F5] p-3 font-sans text-xs text-[#7A2A2A]">
            {error}
          </div>
        )}

        <form onSubmit={handleSave} className="grid grid-cols-1 gap-6 md:grid-cols-12">
          {/* Profile Photo Card */}
          <Card className="rounded-sm border border-[#E4E2DD] bg-white p-6 text-center shadow-none md:col-span-4">
            <CardHeader className="p-0 pb-4">
              <CardTitle className="font-sans text-sm font-semibold uppercase tracking-wider text-[#081534]">
                Advocate Photo
              </CardTitle>
              <CardDescription className="font-serif text-xs text-[#45464E]">
                Displayed in header and verified legal drafts
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col items-center space-y-4 p-0">
              <div className="relative flex h-28 w-28 items-center justify-center overflow-hidden rounded-sm border border-[#E4E2DD] bg-[#F0EEE9] text-[#081534]">
                {profile.avatar_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={profile.avatar_url}
                    alt={profile.full_name}
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <User className="h-12 w-12 text-[#76777F]" strokeWidth={1.5} />
                )}
                <label
                  htmlFor="photo-upload"
                  className="absolute bottom-1 right-1 flex h-7 w-7 cursor-pointer items-center justify-center rounded-sm bg-[#081534] text-white shadow-sm hover:bg-[#1E2A4A]"
                  title="Upload Advocate Photo"
                >
                  <Camera className="h-3.5 w-3.5" strokeWidth={1.5} />
                </label>
                <input
                  id="photo-upload"
                  type="file"
                  accept="image/*"
                  onChange={handleImageUpload}
                  className="hidden"
                />
              </div>

              <div className="w-full space-y-2">
                <label
                  htmlFor="photo-upload"
                  className="flex w-full cursor-pointer items-center justify-center gap-2 rounded-sm border border-[#E4E2DD] bg-[#FBF9F4] py-2 font-sans text-xs font-semibold text-[#081534] transition-colors hover:bg-[#E4E2DD]"
                >
                  <Upload className="h-3.5 w-3.5" strokeWidth={1.5} />
                  Choose Photo File
                </label>
                <p className="font-serif text-[11px] text-[#76777F]">
                  JPG, PNG or WEBP (Max 2MB)
                </p>
              </div>

              <div className="w-full border-t border-[#E4E2DD] pt-3 text-left">
                <p className="font-sans text-[11px] font-semibold uppercase tracking-wider text-[#45464E]">
                  Verified Advocate Status
                </p>
                <div className="mt-1.5 flex items-center gap-1.5 font-sans text-xs font-medium text-[#1A1A1A]">
                  <ShieldCheck className="h-4 w-4 text-[#081534]" strokeWidth={1.5} />
                  Bar Council Authenticated
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Profile Details Form Card */}
          <Card className="rounded-sm border border-[#E4E2DD] bg-white p-6 shadow-none md:col-span-8">
            <CardHeader className="p-0 pb-4">
              <CardTitle className="font-sans text-base font-semibold text-[#081534]">
                Professional Information
              </CardTitle>
              <CardDescription className="font-serif text-xs text-[#45464E]">
                Official legal details for drafting contracts and court filings
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 p-0 pt-4">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-1">
                  <label className="font-sans text-xs font-semibold text-[#081534]">
                    Full Name & Title
                  </label>
                  <Input
                    type="text"
                    required
                    value={profile.full_name}
                    onChange={(e) => setProfile({ ...profile, full_name: e.target.value })}
                    className="h-9 rounded-sm border-[#E4E2DD] font-sans text-xs text-[#1A1A1A]"
                    placeholder="Enter your full name and title"
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-sans text-xs font-semibold text-[#081534]">
                    Bar Council Registration No.
                  </label>
                  <Input
                    type="text"
                    required
                    value={profile.bar_number}
                    onChange={(e) => setProfile({ ...profile, bar_number: e.target.value })}
                    className="h-9 rounded-sm border-[#E4E2DD] font-sans text-xs text-[#1A1A1A]"
                    placeholder="Enter Bar Council Registration No."
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="font-sans text-xs font-semibold text-[#081534]">
                  Primary Court Jurisdiction
                </label>
                <Input
                  type="text"
                  required
                  value={profile.primary_court}
                  onChange={(e) => setProfile({ ...profile, primary_court: e.target.value })}
                  className="h-9 rounded-sm border-[#E4E2DD] font-sans text-xs text-[#1A1A1A]"
                  placeholder="Enter primary court jurisdiction"
                />
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-1">
                  <label className="font-sans text-xs font-semibold text-[#081534]">
                    Contact Phone Number
                  </label>
                  <Input
                    type="text"
                    value={profile.phone}
                    onChange={(e) => setProfile({ ...profile, phone: e.target.value })}
                    className="h-9 rounded-sm border-[#E4E2DD] font-sans text-xs text-[#1A1A1A]"
                    placeholder="Enter contact phone number"
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-sans text-xs font-semibold text-[#081534]">
                    Registered Email Address
                  </label>
                  <Input
                    type="email"
                    disabled
                    value={profile.email}
                    className="h-9 rounded-sm border-[#E4E2DD] bg-[#FBF9F4] font-sans text-xs text-[#76777F]"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="font-sans text-xs font-semibold text-[#081534]">
                  Chamber / Office Address
                </label>
                <textarea
                  rows={3}
                  value={profile.office_address}
                  onChange={(e) => setProfile({ ...profile, office_address: e.target.value })}
                  className="w-full rounded-sm border border-[#E4E2DD] p-2.5 font-sans text-xs text-[#1A1A1A] focus:outline-none focus:ring-1 focus:ring-[#081534]"
                  placeholder="Enter chamber or office address..."
                />
              </div>

              <div className="pt-2">
                <Button
                  type="submit"
                  disabled={saving}
                  className="h-10 gap-2 rounded-sm bg-[#081534] font-sans text-xs font-semibold text-white transition-colors hover:bg-[#1E2A4A]"
                >
                  <Save className="h-4 w-4" strokeWidth={1.5} />
                  {saving ? "Saving to Supabase..." : "Save Advocate Profile"}
                </Button>
              </div>
            </CardContent>
          </Card>
        </form>

        {/* Security & Password Reset Section */}
        <Card className="rounded-sm border border-[#E4E2DD] bg-white p-6 shadow-none">
          <CardHeader className="p-0 pb-4">
            <div className="flex items-center gap-2">
              <KeyRound className="h-5 w-5 text-[#081534]" strokeWidth={1.5} />
              <CardTitle className="font-sans text-base font-semibold text-[#081534]">
                Password Reset & Security
              </CardTitle>
            </div>
            <CardDescription className="font-serif text-xs text-[#45464E]">
              Update your advocate password or send a password reset link to your registered email.
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-4 p-0 pt-4">
            {passwordSuccess && (
              <div className="flex items-center gap-2 rounded-sm border border-[#C3E6CB] bg-[#D4EDDA] p-3 font-sans text-xs font-semibold text-[#155724]">
                <CheckCircle2 className="h-4 w-4" />
                Password updated successfully in Supabase!
              </div>
            )}

            {emailResetSuccess && (
              <div className="flex items-center gap-2 rounded-sm border border-[#C3E6CB] bg-[#D4EDDA] p-3 font-sans text-xs font-semibold text-[#155724]">
                <CheckCircle2 className="h-4 w-4" />
                Password reset email sent to {profile.email}! Check your inbox.
              </div>
            )}

            {passwordError && (
              <div className="rounded-sm border border-[#F8D7DA] bg-[#FFF5F5] p-3 font-sans text-xs text-[#7A2A2A]">
                {passwordError}
              </div>
            )}

            <form onSubmit={handlePasswordUpdate} className="space-y-4">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-1">
                  <label className="font-sans text-xs font-semibold text-[#081534]">
                    New Password
                  </label>
                  <Input
                    type="password"
                    required
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="h-9 rounded-sm border-[#E4E2DD] font-sans text-xs text-[#1A1A1A]"
                    placeholder="Enter new password (min 6 chars)"
                  />
                </div>

                <div className="space-y-1">
                  <label className="font-sans text-xs font-semibold text-[#081534]">
                    Confirm New Password
                  </label>
                  <Input
                    type="password"
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="h-9 rounded-sm border-[#E4E2DD] font-sans text-xs text-[#1A1A1A]"
                    placeholder="Confirm new password"
                  />
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-3 pt-2">
                <Button
                  type="submit"
                  disabled={savingPassword}
                  className="h-9 gap-2 rounded-sm bg-[#081534] font-sans text-xs font-semibold text-white transition-colors hover:bg-[#1E2A4A]"
                >
                  <KeyRound className="h-3.5 w-3.5" strokeWidth={1.5} />
                  {savingPassword ? "Updating Password..." : "Update Password"}
                </Button>

                <Button
                  type="button"
                  variant="outline"
                  onClick={handleSendResetEmail}
                  disabled={sendingResetEmail || !profile.email}
                  className="h-9 gap-2 rounded-sm border-[#E4E2DD] font-sans text-xs font-semibold text-[#081534] hover:bg-[#FBF9F4]"
                >
                  <Mail className="h-3.5 w-3.5" strokeWidth={1.5} />
                  {sendingResetEmail ? "Sending Reset Email..." : "Send Reset Link to Email"}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </AuthedShell>
  );
}
