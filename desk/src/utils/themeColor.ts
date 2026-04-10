/**
 * HD Theme — dynamic color switcher
 *
 * Usage:
 *   import { setHDTheme } from '@/utils/themeColor'
 *   setHDTheme('#7c3aed')          // violet (default)
 *   setHDTheme('#0ea5e9')          // sky blue
 *   setHDTheme('#16a34a')          // green
 *
 * Or from the browser console (no import needed once the app is loaded):
 *   window.setHDTheme('#0ea5e9')
 */

/** Convert a hex color string to { h, s, l } (0-360, 0-100, 0-100). */
function hexToHsl(hex: string): { h: number; s: number; l: number } {
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;

  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  let h = 0;
  let s = 0;
  const l = (max + min) / 2;

  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
      case g: h = ((b - r) / d + 2) / 6; break;
      case b: h = ((r - g) / d + 4) / 6; break;
    }
  }

  return { h: Math.round(h * 360), s: Math.round(s * 100), l: Math.round(l * 100) };
}

/** Generate a 10-step palette hex array (50→900) from an HSL primary. */
function buildPalette(h: number, s: number): string[] {
  // lightness stops: 50, 100, 200, 300, 400, 500, 600, 700, 800, 900
  const stops = [97, 93, 86, 76, 64, 52, 45, 37, 27, 17];
  return stops.map((l) => hslToHex(h, s, l));
}

function hslToHex(h: number, s: number, l: number): string {
  const sl = s / 100;
  const ll = l / 100;
  const a = sl * Math.min(ll, 1 - ll);
  const f = (n: number) => {
    const k = (n + h / 30) % 12;
    const color = ll - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
    return Math.round(255 * color).toString(16).padStart(2, "0");
  };
  return `#${f(0)}${f(8)}${f(4)}`;
}

/** Returns '#ffffff' or a dark color based on the luminance of a hex color. */
function contrastColor(hex: string): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  // Perceived luminance
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.55 ? "#1e1b4b" : "#ffffff";
}

/** Apply a primary color to the whole app by updating :root CSS variables. */
export function setHDTheme(primaryHex: string): void {
  if (!/^#[0-9a-fA-F]{6}$/.test(primaryHex)) {
    console.warn("[HD Theme] Invalid hex color:", primaryHex);
    return;
  }

  const { h, s } = hexToHsl(primaryHex);
  const palette = buildPalette(h, s);
  const names = ["50", "100", "200", "300", "400", "500", "600", "700", "800", "900"];
  const root = document.documentElement;

  names.forEach((name, i) => {
    root.style.setProperty(`--hd-${name}`, palette[i]);
    root.style.setProperty(`--blue-${name}`, palette[i]);
  });

  // Frappe UI semantic tokens
  root.style.setProperty("--surface-blue-1", palette[0]);
  root.style.setProperty("--surface-blue-2", palette[1]);
  root.style.setProperty("--surface-blue-3", palette[6]);
  root.style.setProperty("--outline-blue-1", palette[3]);
  root.style.setProperty("--ink-blue-1",     palette[0]);
  root.style.setProperty("--ink-blue-2",     palette[5]);
  root.style.setProperty("--ink-blue-3",     palette[6]);
  root.style.setProperty("--ink-blue-link",  palette[5]);

  // Contrast text color
  root.style.setProperty("--hd-contrast", contrastColor(palette[6]));

  // Persist across page reloads
  localStorage.setItem("hd-theme-color", primaryHex);
}

/** Default theme color applied to all users on first load. */
export const HD_DEFAULT_THEME = "#7c3aed"; // purple

/** Call once at app startup to restore saved theme, or apply the default purple. */
export function restoreHDTheme(): void {
  setHDTheme(localStorage.getItem("hd-theme-color") || HD_DEFAULT_THEME);
}
