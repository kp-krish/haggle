"use client";

import { useEffect, useState } from "react";

import { THEME_EVENT, THEME_KEY, type ThemeChoice } from "@/lib/theme";

const NEXT: Record<ThemeChoice, ThemeChoice> = { system: "light", light: "dark", dark: "system" };
const LABEL: Record<ThemeChoice, string> = { system: "Auto", light: "Light", dark: "Dark" };

function apply(choice: ThemeChoice) {
  const root = document.documentElement;
  if (choice === "system") delete root.dataset.theme;
  else root.dataset.theme = choice;
  try {
    if (choice === "system") localStorage.removeItem(THEME_KEY);
    else localStorage.setItem(THEME_KEY, choice);
  } catch {
    // Storage blocked (private window): the choice still applies for this visit.
  }
  window.dispatchEvent(new Event(THEME_EVENT));
}

/** Cycles Auto → Light → Dark. "Auto" follows the operating system. */
export function ThemeToggle() {
  const [choice, setChoice] = useState<ThemeChoice>("system");

  useEffect(() => {
    const set = document.documentElement.dataset.theme;
    // Reflect the theme the boot script already applied before paint.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (set === "light" || set === "dark") setChoice(set);
  }, []);

  return (
    <button
      type="button"
      onClick={() => {
        const next = NEXT[choice];
        setChoice(next);
        apply(next);
      }}
      className="hover:text-ink"
      title="Switch between automatic, light and dark"
      aria-label={`Theme: ${LABEL[choice]}. Switch theme`}
    >
      {LABEL[choice]}
    </button>
  );
}
