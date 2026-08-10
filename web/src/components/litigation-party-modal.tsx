"use client";

import React, { useState } from "react";
import { X, UserPlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface LitigationPartyModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (partyData: {
    party_type: string;
    party_name: string;
    party_number: number;
    address?: string;
    advocate_name?: string;
  }) => Promise<void>;
}

export function LitigationPartyModal({
  isOpen,
  onClose,
  onSubmit,
}: LitigationPartyModalProps) {
  const [partyType, setPartyType] = useState("Petitioner");
  const [partyName, setPartyName] = useState("");
  const [partyNumber, setPartyNumber] = useState(1);
  const [address, setAddress] = useState("");
  const [advocateName, setAdvocateName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!partyName.trim()) {
      setError("Party Name is required");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await onSubmit({
        party_type: partyType,
        party_name: partyName.trim(),
        party_number: Number(partyNumber) || 1,
        address: address.trim() || undefined,
        advocate_name: advocateName.trim() || undefined,
      });
      // Reset & close
      setPartyName("");
      setAddress("");
      setAdvocateName("");
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs">
      <div className="w-full max-w-md rounded-sm border border-[#E4E2DD] bg-white p-6 shadow-lg">
        <div className="flex items-center justify-between border-b border-[#E4E2DD] pb-3">
          <div className="flex items-center gap-2">
            <UserPlus className="h-5 w-5 text-[#081534]" />
            <h3 className="font-sans text-base font-semibold text-[#081534]">
              Add Litigation Party
            </h3>
          </div>
          <button
            onClick={onClose}
            className="text-[#76777F] hover:text-[#1A1A1A]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {error && (
          <div className="mt-3 rounded-sm border border-[#F8D7DA] bg-[#FFF5F5] p-2.5 font-sans text-xs text-[#7A2A2A]">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 space-y-4 font-sans text-xs">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="font-semibold text-[#081534]">Party Type</label>
              <select
                value={partyType}
                onChange={(e) => setPartyType(e.target.value)}
                className="h-9 w-full rounded-sm border border-[#E4E2DD] bg-white px-2.5 text-xs text-[#1A1A1A] focus:outline-none focus:ring-1 focus:ring-[#081534]"
              >
                <option value="Petitioner">Petitioner</option>
                <option value="Respondent">Respondent</option>
                <option value="Plaintiff">Plaintiff</option>
                <option value="Defendant">Defendant</option>
                <option value="Intervener">Intervener</option>
              </select>
            </div>

            <div className="space-y-1">
              <label className="font-semibold text-[#081534]">Party No.</label>
              <Input
                type="number"
                min={1}
                value={partyNumber}
                onChange={(e) => setPartyNumber(parseInt(e.target.value) || 1)}
                className="h-9 rounded-sm border-[#E4E2DD] text-xs text-[#1A1A1A]"
              />
            </div>
          </div>

          <div className="space-y-1">
            <label className="font-semibold text-[#081534]">Full Party Name *</label>
            <Input
              type="text"
              required
              placeholder="e.g. M/s Apex Tech Solutions Pvt Ltd"
              value={partyName}
              onChange={(e) => setPartyName(e.target.value)}
              className="h-9 rounded-sm border-[#E4E2DD] text-xs text-[#1A1A1A]"
            />
          </div>

          <div className="space-y-1">
            <label className="font-semibold text-[#081534]">Registered Address (Optional)</label>
            <textarea
              rows={2}
              placeholder="Enter registered business or residential address"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              className="w-full rounded-sm border border-[#E4E2DD] p-2 text-xs text-[#1A1A1A] focus:outline-none focus:ring-1 focus:ring-[#081534]"
            />
          </div>

          <div className="space-y-1">
            <label className="font-semibold text-[#081534]">Representing Advocate / Firm (Optional)</label>
            <Input
              type="text"
              placeholder="e.g. Adv. R. Sharma & Associates"
              value={advocateName}
              onChange={(e) => setAdvocateName(e.target.value)}
              className="h-9 rounded-sm border-[#E4E2DD] text-xs text-[#1A1A1A]"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t border-[#E4E2DD]">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              className="h-8 rounded-sm border-[#E4E2DD] text-xs text-[#45464E]"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={submitting}
              className="h-8 rounded-sm bg-[#081534] text-xs font-semibold text-white hover:bg-[#1E2A4A]"
            >
              {submitting ? "Adding..." : "Add Party"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
