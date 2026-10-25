"use client";

import { useActionState } from "react";

import type { FormState } from "@/app/actions";
import { Button } from "@/components/ui";

/** A one-click server action that shows its error, if any, beside the button. */
export function ActionButton({
  action,
  children,
  pendingLabel,
  variant,
  className,
}: {
  action: () => Promise<FormState>;
  children: React.ReactNode;
  pendingLabel?: string;
  variant?: "primary" | "secondary" | "danger";
  className?: string;
}) {
  const [state, run, pending] = useActionState<FormState>(() => action(), undefined);
  return (
    <form action={run} className="inline-flex items-center gap-2">
      <Button variant={variant} className={className} disabled={pending}>
        {pending && pendingLabel ? pendingLabel : children}
      </Button>
      {state?.error && (
        <span role="alert" className="text-xs text-bad">
          {state.error}
        </span>
      )}
    </form>
  );
}
