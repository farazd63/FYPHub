export const EMAIL_DOMAIN_MESSAGE =
  "Email must include a valid domain, for example name@example.com.";
export const EMAIL_FORMAT_MESSAGE = "Enter a valid email address.";
export const SZABIST_EMAIL_DOMAIN = "szabist-isb.pk";
export const SZABIST_EMAIL_DOMAIN_MESSAGE =
  "Use a SZABIST email ending in @szabist-isb.pk.";

const LOCAL_PART = /^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*$/;
const DOMAIN = /^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+(?:[A-Za-z]{1,63}|xn--[A-Za-z0-9-]{2,59})$/;

export function normalizeEmail(value: string): string {
  return value.trim().toLowerCase();
}

/** Return the inline validation message, or undefined when the address is valid. */
export function emailValidationMessage(value: string): string | undefined {
  const normalized = normalizeEmail(value);
  if (!normalized || /\s/.test(normalized)) return EMAIL_FORMAT_MESSAGE;

  const atCount = (normalized.match(/@/g) ?? []).length;
  if (atCount !== 1) return EMAIL_FORMAT_MESSAGE;

  const [local, domain] = normalized.split("@");
  if (
    !local ||
    !domain ||
    local.includes("..") ||
    domain.includes("..") ||
    local.startsWith(".") ||
    local.endsWith(".") ||
    domain.startsWith(".") ||
    domain.endsWith(".") ||
    !LOCAL_PART.test(local) ||
    !DOMAIN.test(domain)
  ) {
    return EMAIL_DOMAIN_MESSAGE;
  }
  return undefined;
}

/** Return the shared email error plus the single institution-domain rule. */
export function szabistEmailValidationMessage(value: string): string | undefined {
  const formatError = emailValidationMessage(value);
  if (formatError) return formatError;
  const domain = normalizeEmail(value).split("@")[1];
  return domain === SZABIST_EMAIL_DOMAIN ? undefined : SZABIST_EMAIL_DOMAIN_MESSAGE;
}

export function isValidEmail(value: string): boolean {
  return emailValidationMessage(value) === undefined;
}
