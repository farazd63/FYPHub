import { X } from "lucide-react";
import {
  useEffect,
  useId,
  useRef,
  type MouseEvent,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { IconButton } from "./IconButton";

type ModalProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
  closeOnScrim?: boolean;
};

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';

export function Modal({
  open,
  onClose,
  title,
  children,
  footer,
  className,
  closeOnScrim = true,
}: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    const previousActive = document.activeElement as HTMLElement | null;
    const panel = panelRef.current;

    const focusables = panel?.querySelectorAll<HTMLElement>(FOCUSABLE);
    focusables?.[0]?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !panel) return;
      const nodes = panel.querySelectorAll<HTMLElement>(FOCUSABLE);
      if (!nodes.length) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    document.body.classList.add("fy-modal-open");

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.classList.remove("fy-modal-open");
      previousActive?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;

  const onScrimClick = (event: MouseEvent<HTMLDivElement>) => {
    if (closeOnScrim && event.target === event.currentTarget) onClose();
  };

  return createPortal(
    <div className="fy-modal" role="presentation" onMouseDown={onScrimClick}>
      <div
        ref={panelRef}
        className={["fy-modal__panel", className].filter(Boolean).join(" ")}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <header className="fy-modal__header">
          <h2 id={titleId} className="fy-modal__title">
            {title}
          </h2>
          <IconButton label="Close dialog" onClick={onClose} size="sm">
            <X strokeWidth={1.75} size={18} aria-hidden />
          </IconButton>
        </header>
        <div className="fy-modal__body">{children}</div>
        {footer && <footer className="fy-modal__footer">{footer}</footer>}
      </div>
    </div>,
    document.body,
  );
}