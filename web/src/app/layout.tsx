import type { Metadata } from "next";
import { IBM_Plex_Sans, IBM_Plex_Serif } from "next/font/google";
import "./globals.css";
import { cn } from "@/lib/utils";

const ibmPlexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-ibm-sans",
});

const ibmPlexSerif = IBM_Plex_Serif({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-ibm-serif",
});

export const metadata: Metadata = {
  title: "VidhiDesk — AI Legal Assistant",
  description: "AI legal assistant — advocate-reviewed drafting and research.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={cn("font-sans", ibmPlexSans.variable, ibmPlexSerif.variable)}
    >
      <body className="antialiased bg-background text-foreground">{children}</body>
    </html>
  );
}

