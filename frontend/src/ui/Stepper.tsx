import { Check } from "lucide-react";

export type StepperStep = {
  id: string;
  label: string;
};

type StepperProps = {
  steps: StepperStep[];
  currentStepId: string;
  completedStepIds?: string[];
  className?: string;
};

export function Stepper({
  steps,
  currentStepId,
  completedStepIds = [],
  className,
}: StepperProps) {
  const completed = new Set(completedStepIds);

  return (
    <ol className={["fy-stepper", className].filter(Boolean).join(" ")}>
      {steps.map((step, index) => {
        const isCurrent = step.id === currentStepId;
        const isComplete = completed.has(step.id);
        const state = isComplete ? "complete" : isCurrent ? "current" : "upcoming";

        return (
          <li
            key={step.id}
            className={[
              "fy-stepper__item",
              `fy-stepper__item--${state}`,
            ].join(" ")}
          >
            <div className="fy-stepper__marker" aria-hidden>
              {isComplete ? (
                <Check strokeWidth={1.75} size={14} />
              ) : (
                <span>{index + 1}</span>
              )}
            </div>
            <span className="fy-stepper__label">{step.label}</span>
            {index < steps.length - 1 && (
              <span className="fy-stepper__connector" aria-hidden />
            )}
          </li>
        );
      })}
    </ol>
  );
}