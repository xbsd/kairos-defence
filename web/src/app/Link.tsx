import type { ReactNode } from "react";

import { navigate } from "./routes";

/** An in-app link (keeps the browser's own behavior for modified clicks). */
export function Link(props: {
  to: string;
  className?: string;
  children: ReactNode;
  current?: boolean;
}) {
  return (
    <a
      href={props.to}
      className={props.className}
      aria-current={props.current ? "page" : undefined}
      onClick={(e) => {
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
        e.preventDefault();
        navigate(props.to);
      }}
    >
      {props.children}
    </a>
  );
}
