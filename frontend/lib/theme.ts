/**
 * Dark / light theme. Dark is Krama's default look; a visitor's choice is remembered in localStorage.
 * The theme lives on <html>: `data-theme="light"` switches the colour tokens in globals.css, and the
 * `dark` class drives Tailwind's `dark:` variant.
 */
export type Theme = "dark" | "light";

export const THEME_STORAGE_KEY = "krama:theme";

/** Runs in <head> before the first paint, so a light-theme visitor never sees a dark flash. */
export const THEME_INIT_SCRIPT = `(function(){try{if(localStorage.getItem("${THEME_STORAGE_KEY}")==="light"){var d=document.documentElement;d.setAttribute("data-theme","light");d.classList.remove("dark");}}catch(e){}})();`;

export function currentTheme(): Theme {
  if (typeof document === "undefined") return "dark";
  return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
}

export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  root.setAttribute("data-theme", theme);
  root.classList.toggle("dark", theme === "dark");
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // private mode or blocked storage: the theme still applies for this page
  }
}

/** Calls `onChange` whenever the theme on <html> changes (from any toggle on the page). */
export function subscribeTheme(onChange: () => void): () => void {
  if (typeof MutationObserver === "undefined") return () => undefined;
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  return () => observer.disconnect();
}
