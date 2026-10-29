import { useId, useState } from "react";
import { getPasswordGuidance } from "./passwordPolicy";

export { getPasswordGuidance } from "./passwordPolicy";
export type { PasswordCriterion, PasswordStrength } from "./passwordPolicy";

const inputClass = "w-full rounded-lg border border-[#DCE3ED] bg-white px-3.5 py-3 text-base text-[#243746] transition-colors focus:border-[#4663FF] disabled:cursor-not-allowed disabled:bg-[#f4f6f4]";

function PasswordGuidance({ value, id }: { value: string; id: string }) {
  if (!value) return null;
  const { criteria, score, strength } = getPasswordGuidance(value);
  const meterClass = strength === "Weak" ? "bg-[#a43a33]" : strength === "Fair" ? "bg-[#a87518]" : strength === "Strong" ? "bg-[#4663FF]" : "bg-[#176B66]";
  return (
    <div id={id} className="password-guidance grid gap-2 rounded-lg bg-[#f4f8f5] px-3 py-2.5 text-xs text-[#4f6470]">
      <div className="flex items-center gap-2">
        <span className="font-semibold text-[#243746]">Strength estimate: {strength}</span>
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[#d8e2dc]" aria-hidden="true"><div className={`h-full rounded-full ${meterClass}`} style={{ width: `${(score / criteria.length) * 100}%` }} /></div>
      </div>
      <p>Strength is an estimate, not a security guarantee.</p>
      {criteria.some((criterion) => !criterion.met) && <ul className="grid gap-1" aria-label="Password suggestions">{criteria.filter((criterion) => !criterion.met).map((criterion) => <li key={criterion.metLabel}>{criterion.missingLabel}</li>)}</ul>}
    </div>
  );
}

type PasswordFieldProps = { label: string; value: string; onChange: (value: string) => void; autoComplete?: string; disabled?: boolean; error?: string; guidance?: boolean; confirm?: boolean; compact?: boolean };

export function PasswordField({ label, value, onChange, autoComplete = "new-password", disabled, error, guidance, confirm, compact = false }: PasswordFieldProps) {
  const id = useId();
  const errorId = `${id}-error`;
  const guidanceId = `${id}-guidance`;
  const [visible, setVisible] = useState(false);
  const isConfirmation = confirm ?? label.toLowerCase().includes("confirm");
  const showGuidance = guidance ?? (autoComplete === "new-password" && !isConfirmation);
  const describedBy = [error ? errorId : "", showGuidance && value ? guidanceId : ""].filter(Boolean).join(" ") || undefined;
  const fieldClass = compact ? "w-full rounded-lg border border-[#DCE3ED] bg-white px-3 py-2 text-sm text-[#243746] focus:border-[#4663FF]" : inputClass;
  return (
    <div className="grid gap-2">
      <label htmlFor={id} className="text-sm font-semibold">{label}</label>
      <div className="relative">
        <input id={id} className={`${fieldClass} pr-16 ${error ? "border-[#a43a33]" : ""}`} type={visible ? "text" : "password"} value={value} autoComplete={autoComplete} disabled={disabled} aria-invalid={Boolean(error)} aria-describedby={describedBy} onChange={(event) => onChange(event.target.value)} />
        <button type="button" disabled={disabled} aria-controls={id} aria-pressed={visible} aria-label={`${visible ? "Hide" : "Show"} ${label.toLowerCase()}`} onClick={() => setVisible((current) => !current)} className="absolute inset-y-0 right-3 text-xs font-semibold text-[#176B66] disabled:text-[#4f6470]">{visible ? "Hide" : "Show"}</button>
      </div>
      {showGuidance && <PasswordGuidance value={value} id={guidanceId} />}
      {isConfirmation && value && <p id={error ? errorId : undefined} className={error ? "text-sm text-[#a43a33]" : "text-sm text-[#176B66]"}>{error ? "Passwords do not match." : "Passwords match."}</p>}
      {error && (!isConfirmation || !value) && <p id={errorId} className="text-sm text-[#a43a33]">{error}</p>}
    </div>
  );
}
