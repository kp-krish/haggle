"use client";

import { useActionState, useState } from "react";

import type { FormState } from "@/app/actions";
import { Button } from "@/components/ui";

/**
 * A one-click server action that shows its error, if any, beside the button.
 * With `confirm`, the first click asks the question inline and a second click runs it.
 */
export function ActionButton({
  action,
  children,
  pendingLabel,
  variant,
  className,
  confirm,
  confirmLabel = "Yes",
}: {
  action: () => Promise<FormState>;
  children: React.ReactNode;
  pendingLabel?: string;
  variant?: "primary" | "secondary" | "danger" | "quiet";
  className?: string;
  confirm?: string;
  confirmLabel?: string;
}) {
  const [state, run, pending] = useActionState<FormState>(() => action(), undefined);
  const [asking, setAsking] = useState(false);

  if (confirm && !asking && !pending) {
    return (
      <Button type="button" variant={variant} className={className} onClick={() => setAsking(true)}>
        {children}
      </Button>
    );
  }
  return (
    <form action={run} className="inline-flex flex-wrap items-center gap-x-3 gap-y-1">
      {confirm && <span className="text-sm">{confirm}</span>}
      <Button variant={confirm ? "danger" : variant} className={confirm ? "px-3 py-1 text-sm" : className} disabled={pending}>
        {pending && pendingLabel ? pendingLabel : confirm ? confirmLabel : children}
      </Button>
      {confirm && !pending && (
        <Button type="button" variant="quiet" onClick={() => setAsking(false)}>
          Keep it
        </Button>
      )}
      {state?.error && (
        <span role="alert" className="text-[13px] text-bad">
          {state.error}
        </span>
      )}
    </form>
  );
}
