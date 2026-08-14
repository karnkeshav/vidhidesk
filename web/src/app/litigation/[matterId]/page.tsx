"use client";

import { useParams } from "next/navigation";
import { MatterWorkspace } from "@/components/matter-workspace";

export default function LitigationMatterPage() {
  const params = useParams<{ matterId: string }>();
  return <MatterWorkspace matterId={params.matterId} />;
}
