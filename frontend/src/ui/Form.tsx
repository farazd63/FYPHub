import { AlertCircle, Upload } from "lucide-react";
import {
  useCallback,
  useId,
  useRef,
  useState,
  type ChangeEvent,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";

type FieldProps = {
  label: string;
  htmlFor?: string;
  help?: string;
  error?: string;
  required?: boolean;
  children: ReactNode;
  className?: string;
};

export function Field({
  label,
  htmlFor,
  help,
  error,
  required,
  children,
  className,
}: FieldProps) {
  const autoId = useId();
  const fieldId = htmlFor ?? autoId;
  const helpId = help ? `${fieldId}-help` : undefined;
  const errorId = error ? `${fieldId}-error` : undefined;

  return (
    <div className={["fy-field", className].filter(Boolean).join(" ")}>
      <label className="fy-field__label" htmlFor={fieldId}>
        {label}
        {required && (
          <span className="fy-field__required" aria-hidden>
            {" "}
            *
          </span>
        )}
      </label>
      <div className="fy-field__control">{children}</div>
      {help && (
        <p id={helpId} className="fy-field__help">
          {help}
        </p>
      )}
      {error && (
        <p id={errorId} className="fy-field__error" role="alert">
          <AlertCircle strokeWidth={1.75} size={14} aria-hidden />
          <span>{error}</span>
        </p>
      )}
    </div>
  );
}

export function fieldDescribedBy(help?: string, error?: string, fieldId?: string) {
  const parts: string[] = [];
  if (help && fieldId) parts.push(`${fieldId}-help`);
  if (error && fieldId) parts.push(`${fieldId}-error`);
  return parts.length ? parts.join(" ") : undefined;
}

type ControlProps = { error?: boolean; describedBy?: string };

export function Input({
  error,
  describedBy,
  className,
  id,
  ...rest
}: InputHTMLAttributes<HTMLInputElement> & ControlProps) {
  const autoId = useId();
  const fieldId = id ?? autoId;
  return (
    <input
      id={fieldId}
      className={["fy-input", error && "fy-input--error", className]
        .filter(Boolean)
        .join(" ")}
      aria-invalid={error ? true : undefined}
      aria-describedby={describedBy}
      {...rest}
    />
  );
}

export function Select({
  error,
  describedBy,
  className,
  children,
  id,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement> & ControlProps) {
  const autoId = useId();
  return (
    <select
      id={id ?? autoId}
      className={["fy-input", "fy-select", error && "fy-input--error", className]
        .filter(Boolean)
        .join(" ")}
      aria-invalid={error ? true : undefined}
      aria-describedby={describedBy}
      {...rest}
    >
      {children}
    </select>
  );
}

export function Textarea({
  error,
  describedBy,
  className,
  id,
  ...rest
}: TextareaHTMLAttributes<HTMLTextAreaElement> & ControlProps) {
  const autoId = useId();
  return (
    <textarea
      id={id ?? autoId}
      className={["fy-input", "fy-textarea", error && "fy-input--error", className]
        .filter(Boolean)
        .join(" ")}
      aria-invalid={error ? true : undefined}
      aria-describedby={describedBy}
      {...rest}
    />
  );
}

type CheckboxProps = Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {
  label: ReactNode;
};

export function Checkbox({ label, className, id: propId, ...rest }: CheckboxProps) {
  const id = propId ?? useId();
  return (
    <label className={["fy-check", className].filter(Boolean).join(" ")} htmlFor={id}>
      <input type="checkbox" id={id} className="fy-check__input" {...rest} />
      <span className="fy-check__box" aria-hidden />
      <span className="fy-check__label">{label}</span>
    </label>
  );
}

type RadioProps = Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {
  label: ReactNode;
};

export function Radio({ label, className, id: propId, ...rest }: RadioProps) {
  const id = propId ?? useId();
  return (
    <label className={["fy-radio", className].filter(Boolean).join(" ")} htmlFor={id}>
      <input type="radio" id={id} className="fy-radio__input" {...rest} />
      <span className="fy-radio__dot" aria-hidden />
      <span className="fy-radio__label">{label}</span>
    </label>
  );
}

type SwitchProps = {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label: string;
  disabled?: boolean;
  id?: string;
  className?: string;
};

export function Switch({
  checked,
  onCheckedChange,
  label,
  disabled,
  id: propId,
  className,
}: SwitchProps) {
  const id = propId ?? useId();
  return (
    <label
      className={["fy-switch", className].filter(Boolean).join(" ")}
      htmlFor={id}
    >
      <span className="fy-switch__label">{label}</span>
      <input
        type="checkbox"
        role="switch"
        id={id}
        className="fy-switch__input"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onCheckedChange(e.target.checked)}
      />
      <span className="fy-switch__track" aria-hidden>
        <span className="fy-switch__thumb" />
      </span>
    </label>
  );
}

type DateFieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, "type"> &
  ControlProps;

export function DateField({
  error,
  describedBy,
  className,
  id,
  ...rest
}: DateFieldProps) {
  const autoId = useId();
  return (
    <input
      type="date"
      id={id ?? autoId}
      className={["fy-input", "fy-date", error && "fy-input--error", className]
        .filter(Boolean)
        .join(" ")}
      aria-invalid={error ? true : undefined}
      aria-describedby={describedBy}
      {...rest}
    />
  );
}

type FileUploadProps = {
  accept?: string;
  multiple?: boolean;
  disabled?: boolean;
  onFiles: (files: FileList) => void;
  label?: string;
  hint?: string;
  className?: string;
};

export function FileUpload({
  accept,
  multiple,
  disabled,
  onFiles,
  label = "Drop files here or click to browse",
  hint,
  className,
}: FileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const pickFiles = useCallback(
    (files: FileList | null) => {
      if (files?.length) onFiles(files);
    },
    [onFiles],
  );

  const onChange = (event: ChangeEvent<HTMLInputElement>) => {
    pickFiles(event.target.files);
    event.target.value = "";
  };

  return (
    <div
      className={[
        "fy-file-upload",
        dragOver && "fy-file-upload--active",
        disabled && "fy-file-upload--disabled",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        if (!disabled) pickFiles(e.dataTransfer.files);
      }}
    >
      <input
        ref={inputRef}
        type="file"
        className="fy-file-upload__input"
        accept={accept}
        multiple={multiple}
        disabled={disabled}
        onChange={onChange}
        tabIndex={-1}
      />
      <button
        type="button"
        className="fy-file-upload__trigger"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
      >
        <Upload strokeWidth={1.75} size={20} aria-hidden />
        <span className="fy-file-upload__label">{label}</span>
        {hint && <span className="fy-file-upload__hint">{hint}</span>}
      </button>
    </div>
  );
}