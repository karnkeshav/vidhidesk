"use client";

import { ReactNode } from "react";

export function LegalDocumentSheet({
  title,
  subtitle,
  children,
  fullText,
}: {
  title?: string;
  subtitle?: string;
  children?: ReactNode;
  fullText?: string;
}) {
  return (
    <div className="flex flex-1 justify-center overflow-y-auto bg-[#F6F3EE] py-6 md:py-8">
      <article className="w-full max-w-[800px] border border-[#E4E2DD] bg-white p-6 md:p-10 font-serif text-sm md:text-base leading-[1.7] text-[#1A1A1A] shadow-[0_2px_8px_rgba(0,0,0,0.04)] rounded-sm">
        {title && (
          <h2 className="mb-6 text-center font-sans text-xl font-semibold uppercase tracking-tight text-[#081534] underline decoration-1 underline-offset-4">
            {title}
          </h2>
        )}
        {subtitle && (
          <p className="mb-6 font-serif text-xs italic text-[#45464E]">
            {subtitle}
          </p>
        )}

        {fullText ? (
          <div className="whitespace-pre-wrap font-serif text-sm leading-[1.7] text-[#1A1A1A]">
            {fullText}
          </div>
        ) : (
          children
        )}
      </article>
    </div>
  );
}
