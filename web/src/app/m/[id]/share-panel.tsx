"use client";

import { useState, useTransition } from "react";
import type { MemoryRow } from "@/lib/supabase/database.types";
import { updatePrivacyAction } from "./actions";

export function SharePanel({ memory }: { memory: MemoryRow }) {
  const [privacy, setPrivacy] = useState(memory.privacy);
  const [copied, setCopied] = useState(false);
  const [isPending, startTransition] = useTransition();

  const shareUrl =
    privacy === "link" && memory.share_token
      ? `${typeof window !== "undefined" ? window.location.origin : ""}/s/${memory.share_token}`
      : null;

  const toggle = () => {
    const next = privacy === "link" ? "private" : "link";
    setPrivacy(next);
    startTransition(async () => {
      await updatePrivacyAction(memory.id, next);
    });
  };

  const copy = async () => {
    if (!shareUrl) return;
    await navigator.clipboard.writeText(shareUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="card p-5">
      <h3 className="font-semibold">Sharing</h3>
      <p className="text-sm text-[color:var(--muted)] mt-1">
        {privacy === "private"
          ? "Only you can see this memory."
          : "Anyone with the link can view this memory."}
      </p>
      <button
        type="button"
        onClick={toggle}
        disabled={isPending}
        className="btn btn-ghost mt-4 text-sm"
      >
        {privacy === "link" ? "Make private" : "Create share link"}
      </button>
      {shareUrl && (
        <div className="mt-4 flex gap-2">
          <input
            readOnly
            value={shareUrl}
            className="input text-xs font-mono"
            onFocus={(e) => e.currentTarget.select()}
          />
          <button
            type="button"
            onClick={copy}
            className="btn btn-primary text-sm whitespace-nowrap"
          >
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      )}
    </div>
  );
}
