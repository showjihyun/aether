"use client";

import { useState } from "react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { shortId } from "@/lib/format";

/** DESIGN.md 6절: ID 는 `font-mono text-xs`, 앞 8자 + `…`, 클릭으로 복사, tooltip "복사됨". */
export function CopyableId({ id }: { id: string }) {
  const [copied, setCopied] = useState(false);

  return (
    <Tooltip open={copied} onOpenChange={(open) => !open && setCopied(false)}>
      <TooltipTrigger asChild>
        <button
          type="button"
          title={id}
          className="font-mono text-xs"
          onClick={() => {
            void navigator.clipboard.writeText(id).then(() => setCopied(true));
          }}
        >
          {shortId(id)}
        </button>
      </TooltipTrigger>
      <TooltipContent>복사됨</TooltipContent>
    </Tooltip>
  );
}
