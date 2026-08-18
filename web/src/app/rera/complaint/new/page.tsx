"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { AuthedShell } from "@/components/authed-shell";
import { Button } from "@/components/ui/button";
import { createMatter, listTemplates } from "@/lib/api";
import { Home, ArrowRight, ShieldCheck, Clock, FileText, AlertCircle } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";

export default function ReraComplaintNewPage() {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleStartComplaint() {
    setIsSubmitting(true);
    setError(null);
    try {
      const templates = await listTemplates();
      const t = templates.find(t => t.category === "rera" && t.template_key === "rera-complaint");
      if (!t) {
        throw new Error("RERA Complaint template not found in the system.");
      }
      
      const matter = await createMatter({
        title: "RERA Complaint - Delay in Possession",
        module: "rera",
        template_id: t.id
      });
      
      router.push(`/rera/${matter.id}`);
    } catch (err: unknown) {
      console.error(err);
      setError(err instanceof Error ? err.message : "An unexpected error occurred.");
      setIsSubmitting(false);
    }
  }

  return (
    <AuthedShell>
      <div className="max-w-4xl mx-auto py-12 px-6">
        <div className="text-center mb-12">
          <div className="inline-flex items-center justify-center p-3 bg-blue-50 text-[#081534] rounded-full mb-6">
            <Home className="w-8 h-8" />
          </div>
          <h1 className="text-4xl font-bold text-[#081534] tracking-tight mb-4">
            RERA Complaint Intake
          </h1>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Delay in Possession of Real Estate Project
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-12">
          <Card className="border-[#E5E3DE] shadow-sm">
            <CardHeader>
              <Clock className="w-8 h-8 text-[#081534] mb-2" />
              <CardTitle className="text-lg">Save Time</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-gray-600">
              Draft formal RERA complaints in minutes using our guided intelligent intake process tailored for possession delays.
            </CardContent>
          </Card>
          
          <Card className="border-[#E5E3DE] shadow-sm">
            <CardHeader>
              <ShieldCheck className="w-8 h-8 text-[#081534] mb-2" />
              <CardTitle className="text-lg">Legally Robust</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-gray-600">
              Generates documents compliant with RERA regulations, backed by structured legal phrasing and verified precedents.
            </CardContent>
          </Card>
          
          <Card className="border-[#E5E3DE] shadow-sm">
            <CardHeader>
              <FileText className="w-8 h-8 text-[#081534] mb-2" />
              <CardTitle className="text-lg">Ready to File</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-gray-600">
              Export completed complaints directly into standard formats required by state RERA authorities.
            </CardContent>
          </Card>
        </div>

        <Card className="border-[#081534] border-2 shadow-md bg-[#FBF9F5]">
          <CardHeader className="border-b border-[#E5E3DE] pb-6">
            <CardTitle className="text-2xl text-[#081534]">Begin New Matter</CardTitle>
            <CardDescription className="text-base text-gray-600">
              You are about to start a new RERA complaint matter specifically for <strong>Delay in Possession</strong>. 
              This will create a new workspace where you can enter builder details, project details, and payment histories.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            {error && (
              <div className="mb-6 p-4 bg-[#ba1a1a]/10 text-[#ba1a1a] rounded-md flex items-start gap-3">
                <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                <p className="text-sm font-medium">{error}</p>
              </div>
            )}
            <ul className="space-y-3 text-sm text-gray-700">
              <li className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-[#081534]" />
                Requires builder and project registration details.
              </li>
              <li className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-[#081534]" />
                Requires dates of agreement and promised possession.
              </li>
              <li className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-[#081534]" />
                You can save your progress and return at any time.
              </li>
            </ul>
          </CardContent>
          <CardFooter className="bg-white/50 border-t border-[#E5E3DE] p-6">
            <Button 
              size="lg" 
              className="w-full sm:w-auto bg-[#081534] hover:bg-[#081534]/90 text-white gap-2 font-medium"
              onClick={handleStartComplaint}
              disabled={isSubmitting}
            >
              {isSubmitting ? "Creating Workspace..." : "Start Complaint Workspace"}
              {!isSubmitting && <ArrowRight className="w-5 h-5" />}
            </Button>
          </CardFooter>
        </Card>
      </div>
    </AuthedShell>
  );
}
