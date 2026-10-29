export const PASSWORD_MIN_LENGTH = 8;
export const PASSWORD_MAX_LENGTH = 128;

export type PasswordStrength = "Weak" | "Fair" | "Strong" | "Very Strong";

export type PasswordCriterion = {
  met: boolean;
  metLabel: string;
  missingLabel: string;
};

export function getPasswordGuidance(password: string): {
  criteria: PasswordCriterion[];
  strength: PasswordStrength;
  score: number;
} {
  const criteria: PasswordCriterion[] = [
    { met: password.length >= PASSWORD_MIN_LENGTH, metLabel: "At least 8 characters.", missingLabel: "Use at least 8 characters." },
    { met: /[A-Z]/.test(password), metLabel: "Uppercase letter (A–Z).", missingLabel: "Add an uppercase letter (A–Z)." },
    { met: /[a-z]/.test(password), metLabel: "Lowercase letter (a–z).", missingLabel: "Add a lowercase letter (a–z)." },
    { met: /[0-9]/.test(password), metLabel: "Number (0–9).", missingLabel: "Add a number (0–9)." },
    { met: /[^A-Za-z0-9]/.test(password), metLabel: "Special character, such as @, #, or !.", missingLabel: "Add a special character, such as @, #, or !." },
  ];
  const score = criteria.filter((criterion) => criterion.met).length;
  const strength: PasswordStrength = score <= 1 ? "Weak" : score === 2 ? "Fair" : score < criteria.length ? "Strong" : "Very Strong";
  return { criteria, score, strength };
}

export function passwordPolicyError(password: string): string | undefined {
  if (password.length > PASSWORD_MAX_LENGTH) return "Password must be no more than 128 characters.";
  return getPasswordGuidance(password).criteria.find((criterion) => !criterion.met)?.missingLabel;
}
