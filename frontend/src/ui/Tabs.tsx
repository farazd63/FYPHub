import {
  createContext,
  useContext,
  useId,
  type ReactNode,
  type KeyboardEvent,
} from "react";

type TabsContextValue = {
  value: string;
  setValue: (value: string) => void;
  baseId: string;
};

const TabsContext = createContext<TabsContextValue | null>(null);

function useTabsContext() {
  const ctx = useContext(TabsContext);
  if (!ctx) throw new Error("Tabs compound components must be used within Tabs");
  return ctx;
}

type TabsProps = {
  value: string;
  onValueChange: (value: string) => void;
  children: ReactNode;
  className?: string;
  "aria-label"?: string;
};

export function Tabs({
  value,
  onValueChange,
  children,
  className,
  "aria-label": ariaLabel,
}: TabsProps) {
  const baseId = useId();
  return (
    <TabsContext.Provider value={{ value, setValue: onValueChange, baseId }}>
      <div className={["fy-tabs", className].filter(Boolean).join(" ")}>
        {ariaLabel && <span className="fy-sr-only">{ariaLabel}</span>}
        {children}
      </div>
    </TabsContext.Provider>
  );
}

type TabListProps = { children: ReactNode; className?: string };

export function TabList({ children, className }: TabListProps) {
  return (
    <div role="tablist" className={["fy-tabs__list", className].filter(Boolean).join(" ")}>
      {children}
    </div>
  );
}

type TabProps = {
  value: string;
  children: ReactNode;
  disabled?: boolean;
  className?: string;
};

export function Tab({ value, children, disabled, className }: TabProps) {
  const { value: active, setValue, baseId } = useTabsContext();
  const selected = active === value;
  const tabId = `${baseId}-tab-${value}`;
  const panelId = `${baseId}-panel-${value}`;

  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (!disabled) setValue(value);
    }
  };

  return (
    <button
      type="button"
      role="tab"
      id={tabId}
      aria-selected={selected}
      aria-controls={panelId}
      tabIndex={selected ? 0 : -1}
      disabled={disabled}
      className={[
        "fy-tabs__tab",
        selected && "fy-tabs__tab--active",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      onClick={() => !disabled && setValue(value)}
      onKeyDown={onKeyDown}
    >
      {children}
    </button>
  );
}

type TabPanelProps = {
  value: string;
  children: ReactNode;
  className?: string;
};

export function TabPanel({ value, children, className }: TabPanelProps) {
  const { value: active, baseId } = useTabsContext();
  if (active !== value) return null;
  const tabId = `${baseId}-tab-${value}`;
  const panelId = `${baseId}-panel-${value}`;

  return (
    <div
      role="tabpanel"
      id={panelId}
      aria-labelledby={tabId}
      className={["fy-tabs__panel", className].filter(Boolean).join(" ")}
    >
      {children}
    </div>
  );
}