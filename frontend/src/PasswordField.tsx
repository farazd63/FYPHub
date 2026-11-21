import { useId, useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { getPasswordGuidance } from "./passwordPolicy";
import { IconButton } from "./ui/IconButton";

export { getPasswordGuidance } from "./passwordPolicy";
export type { PasswordCriterion, PasswordStrength } from "./passwordPolicy";

const inputClass = "w-full rounded-lg border border-fy-border bg-fy-page px-3.5 py-3 text-base text-fy-text transition-colors focus:border-fy-brand disabled:cursor-not-allowed disabled:bg-fy-surface-muted";

function PasswordGuidance({ value, id }: { value: string; id: string }) {
  if (!value) return null;
  const { criteria, score, strength } = getPasswordGuidance(value);
  const meterClass = strength === "Weak" ? "bg-fy-danger" : strength === "Fair" ? "bg-fy-warning" : strength === "Strong" ? "bg-fy-brand" : "bg-fy-success";
  return (
    <div id={id} className="password-guidance grid gap-2 rounded-lg border border-fy-border bg-fy-page px-3 py-2.5 text-xs text-fy-text-secondary">
      <div className="flex items-center gap-2">
        <span className="font-semibold text-fy-text">Strength estimate: {strength}</span>
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-fy-surface-muted" aria-hidden="true"><div className={`h-full rounded-full ${meterClass}`} style={{ width: `${(score / criteria.length) * 100}%` }} /></div>
      </div>
      <p>Strength is an estimate, not a security guarantee.</p>
      {criteria.some((criterion) => !criterion.met) && <ul className="grid gap-1" aria-label="Password suggestions">{criteria.filter((criterion) => !criterion.met).map((criterion) => <li key={criterion.metLabel}>{criterion.missingLabel}</li>)}</ul>}
    </div>
  );
}

type PasswordFieldProps = { label: string; value: string; onChange: (value: string) => void; autoComplete?: string; disabled?: boolean; error?: string; guidance?: boolean; confirm?: boolean; compact?: boolean; required?: boolean };

export function PasswordField({ label, value, onChange, autoComplete = "new-password", disabled, error, guidance, confirm, compact = false, required = false }: PasswordFieldProps) {
  const id = useId();
  const errorId = `${id}-error`;
  const guidanceId = `${id}-guidance`;
  const [visible, setVisible] = useState(false);
  const isConfirmation = confirm ?? label.toLowerCase().includes("confirm");
  const showGuidance = guidance ?? (autoComplete === "new-password" && !isConfirmation);
  const describedBy = [error ? errorId : "", showGuidance && value ? guidanceId : ""].filter(Boolean).join(" ") || undefined;
  const fieldClass = compact ? "w-full rounded-lg border border-fy-border bg-fy-page px-3 py-2 text-sm text-fy-text focus:border-fy-brand" : inputClass;
  return (
    <div className="grid gap-2">
      <label htmlFor={id} className="text-sm font-semibold">{label}{required && <span className="auth-field__required" aria-hidden="true"> *</span>}</label>
      <div className="relative">
        <input id={id} className={`${fieldClass} pr-16 ${error ? "border-fy-danger" : ""}`} type={visible ? "text" : "password"} value={value} autoComplete={autoComplete} disabled={disabled} required={required} aria-required={required} aria-invalid={Boolean(error)} aria-describedby={describedBy} onChange={(event) => onChange(event.target.value)} />
        <IconButton disabled={disabled} aria-controls={id} aria-pressed={visible} label={`${visible ? "Hide" : "Show"} ${label.toLowerCase()}`} onClick={() => setVisible((current) => !current)} className="password-field__toggle" size="sm" variant="ghost">{visible ? <EyeOff size={16} strokeWidth={1.8} aria-hidden /> : <Eye size={16} strokeWidth={1.8} aria-hidden />}</IconButton>
      </div>
      {showGuidance && <PasswordGuidance value={value} id={guidanceId} />}
      {isConfirmation && value && <p id={error ? errorId : undefined} className={error ? "text-sm text-fy-danger" : "text-sm text-fy-success"}>{error ? "Passwords do not match." : "Passwords match."}</p>}
      {error && (!isConfirmation || !value) && <p id={errorId} className="text-sm text-fy-danger">{error}</p>}
    </div>
  );
}
