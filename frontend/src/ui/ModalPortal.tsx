import { createPortal } from "react-dom";
import type { ReactNode } from "react";

/**
 * Renders workflow dialogs outside portal-shell stacking contexts.
 *
 * The shared portal shells intentionally isolate their content panes for
 * layout. A fixed dialog rendered inside one of those panes can otherwise be
 * clipped below the navigation rail, even with a high z-index.
 */
export function ModalPortal({ children }: { children: ReactNode }) {
  return createPortal(<div className="modal-portal-root">{children}</div>, document.body);
}
