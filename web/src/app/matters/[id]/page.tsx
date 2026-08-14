"use client";

import { useParams } from "next/navigation";
import { MatterWorkspace } from "@/components/matter-workspace";

export default function MatterWorkspacePage() {
  const params = useParams<{ id: string }>();
  return <MatterWorkspace matterId={params.id} />;
}
