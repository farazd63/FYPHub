import { X } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { IconButton } from "./IconButton";

export type ToastTone = "neutral" | "success" | "warning" | "danger" | "info";

export type ToastItem = {
  id: string;
  title?: string;
  message: string;
  tone?: ToastTone;
  durationMs?: number;
};

type ToastContextValue = {
  push: (item: Omit<ToastItem, "id">) => void;
  dismiss: (id: string) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}

let toastCounter = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: string) => {
    setItems((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const push = useCallback(
    (item: Omit<ToastItem, "id">) => {
      const id = `toast-${++toastCounter}`;
      const next: ToastItem = { ...item, id };
      setItems((prev) => [...prev, next]);
      const duration = item.durationMs ?? 5000;
      window.setTimeout(() => dismiss(id), duration);
    },
    [dismiss],
  );

  const value = useMemo(() => ({ push, dismiss }), [push, dismiss]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      {createPortal(
        <div className="fy-toast-region" aria-live="polite" aria-relevant="additions">
          {items.map((item) => (
            <ToastView key={item.id} item={item} onDismiss={() => dismiss(item.id)} />
          ))}
        </div>,
        document.body,
      )}
    </ToastContext.Provider>
  );
}

function ToastView({
  item,
  onDismiss,
}: {
  item: ToastItem;
  onDismiss: () => void;
}) {
  const tone = item.tone ?? "neutral";
  return (
    <div className={["fy-toast", `fy-toast--${tone}`].join(" ")} role="status">
      <div className="fy-toast__content">
        {item.title && <p className="fy-toast__title">{item.title}</p>}
        <p className="fy-toast__message">{item.message}</p>
      </div>
      <IconButton label="Dismiss notification" size="sm" onClick={onDismiss}>
        <X strokeWidth={1.75} size={16} aria-hidden />
      </IconButton>
    </div>
  );
}