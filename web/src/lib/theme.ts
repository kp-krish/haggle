/** Theme choice: "system" follows the OS; "light"/"dark" pin it via data-theme on <html>. */

export type ThemeChoice = "system" | "light" | "dark";

export const THEME_KEY = "haggle-theme";
export const THEME_EVENT = "haggle-theme-change";

/**
 * Runs in <head> before the page paints, so a saved choice never flashes the wrong
 * theme. Kept tiny and dependency-free on purpose.
 */
export const themeBootScript = `try{var t=localStorage.getItem("${THEME_KEY}");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;

export function isDark(): boolean {
  const set = document.documentElement.dataset.theme;
  if (set === "dark") return true;
  if (set === "light") return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}
