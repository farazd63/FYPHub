const FULL_NAME = /^[\p{L}]+(?:[ '\u2019-][\p{L}]+)*$/u;

export function normalizeFullName(value: string): string {
  return value.trim().replace(/\s+/g, " ");
}

export function fullNameValidationMessage(value: string): string | undefined {
  const normalized = normalizeFullName(value);
  if (!normalized) return "Enter a full name.";
  if (normalized.length < 2 || normalized.length > 100) return "Full name must be between 2 and 100 characters.";
  if (!FULL_NAME.test(normalized)) return "Full name may contain letters, spaces, apostrophes, and hyphens only.";
  return undefined;
}

export function academicTextValidationMessage(value: string, label: string, maxLength = 10000): string | undefined {
  const normalized = value.trim();
  if (!normalized) return `${label} is required.`;
  if (normalized.length > maxLength) return `${label} must be no more than ${maxLength} characters.`;
  if (/<\/?[a-z][^>]*>|javascript\s*:/i.test(normalized) || [...normalized].some((character) => { const code = character.charCodeAt(0); return code < 32 && ![9, 10, 13].includes(code); })) return `${label} contains invalid characters.`;
  return undefined;
}
