"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Template } from "@/lib/api";

// Gate shown when someone tries to use a template whose clauses haven't
// all been through the admin clause-review workflow (Keep / Redraft /
// Delete) yet. A template stuck on "beta" always has at least one
// unreviewed clause, so sending them to /admin/templates/[key] always has
// something for them to act on.
export function TemplateReviewGateDialog({
  template,
  onOpenChange,
}: {
  template: Template | null;
  onOpenChange: (open: boolean) => void;
}) {
  const router = useRouter();

  return (
    <Dialog open={template !== null} onOpenChange={onOpenChange}>
      <DialogContent className="rounded-sm border-[#E4E2DD] bg-white sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="font-sans text-base text-[#081534]">
            Clause review required before drafting
          </DialogTitle>
          <DialogDescription className="font-serif text-sm text-[#45464E]">
            {template?.name ?? "This template"} is still marked{" "}
            <strong>Beta — pending clause review</strong>. Before it can be used to
            generate a client draft, go through every clause in the template and
            decide, one by one:
          </DialogDescription>
        </DialogHeader>
        <ul className="list-disc space-y-1 pl-5 font-serif text-sm text-[#1A1A1A]">
          <li><strong>Keep</strong> — the boilerplate is correct as written.</li>
          <li><strong>Redraft</strong> — replace it with corrected text.</li>
          <li><strong>Delete</strong> — remove it from future drafts, with a note why.</li>
        </ul>
        <p className="font-serif text-xs text-[#76777F]">
          Once every clause has a decision, this template flips to &ldquo;Reviewed&rdquo; and
          becomes available to start a matter from.
        </p>
        <DialogFooter>
          <Button
            variant="outline"
            className="rounded-sm border-[#E4E2DD] font-sans text-xs font-semibold text-[#081534]"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            className="rounded-sm bg-[#081534] font-sans text-xs font-semibold text-white hover:bg-[#1E2A4A]"
            onClick={() => {
              if (template?.template_key) {
                router.push(`/admin/templates/${template.template_key}`);
              }
            }}
            disabled={!template?.template_key}
          >
            Go to clause review
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
