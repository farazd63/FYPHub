import { useEffect } from "react";
import { createPortal } from "react-dom";
import { Plus, X } from "lucide-react";
import "./admin-add-button.css";

type Props = {
  open: boolean;
  onClick: () => void;
  label: string;
};

export function AdminAddButton({ open, onClick, label }: Props) {
  const action = open ? `Close ${label}` : `Add ${label}`;

  useEffect(() => {
    if (!open) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClick();
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [onClick, open]);

  return (
    <>
      {open && createPortal(<div className="admin-add-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClick(); }} />, document.body)}
      <button
        type="button"
        className="admin-add-button"
        aria-expanded={open}
        aria-label={action}
        title={action}
        onClick={onClick}
      >
        {open ? <X size={18} aria-hidden="true" /> : <Plus size={18} aria-hidden="true" />}
        <span>{open ? "Close" : "Add"}</span>
      </button>
    </>
  );
}
