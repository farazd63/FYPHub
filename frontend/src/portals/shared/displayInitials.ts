/** Two-letter avatar initials from a display name (grapheme-safe). */
export function displayInitials(name: string, fallback = "?"): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return parts
      .slice(0, 2)
      .map((part) => Array.from(part)[0] ?? "")
      .join("")
      .toUpperCase();
  }
  if (parts.length === 1) {
    const chars = Array.from(parts[0]);
    return (chars.slice(0, 2).join("") || fallback).toUpperCase();
  }
  return fallback;
}