import { Check } from "lucide-react";
import type { ReactNode } from "react";

export type TimelineMilestone = {
  id: string;
  title: string;
  description?: string;
  dateLabel?: string;
  complete?: boolean;
  current?: boolean;
  content?: ReactNode;
};

type TimelineProps = {
  milestones: TimelineMilestone[];
  className?: string;
};

export function Timeline({ milestones, className }: TimelineProps) {
  return (
    <ol className={["fy-timeline", className].filter(Boolean).join(" ")}>
      {milestones.map((item, index) => {
        const state = item.complete
          ? "complete"
          : item.current
            ? "current"
            : "upcoming";
        return (
          <li
            key={item.id}
            className={["fy-timeline__item", `fy-timeline__item--${state}`].join(" ")}
          >
            <div className="fy-timeline__rail" aria-hidden>
              <span className="fy-timeline__dot">
                {item.complete ? (
                  <Check strokeWidth={1.75} size={12} />
                ) : (
                  <span className="fy-timeline__dot-inner" />
                )}
              </span>
              {index < milestones.length - 1 && (
                <span className="fy-timeline__line" />
              )}
            </div>
            <div className="fy-timeline__content">
              <div className="fy-timeline__meta">
                <h4 className="fy-timeline__title">{item.title}</h4>
                {item.dateLabel && (
                  <time className="fy-timeline__date">{item.dateLabel}</time>
                )}
              </div>
              {item.description && (
                <p className="fy-timeline__desc">{item.description}</p>
              )}
              {item.content}
            </div>
          </li>
        );
      })}
    </ol>
  );
}