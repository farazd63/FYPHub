import { useId, useState } from "react";

type Member = {
  id: string;
  name: string;
  registration: string;
  email: string;
};

type Details = {
  name: string;
  registration: string;
  email: string;
};

const STEPS = ["Account Details", "Login Details", "Team Members"];
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const INPUT =
  "w-full rounded-lg border border-[#cbd6d0] bg-white px-3.5 py-3 text-base text-[#243746] transition-colors focus:border-[#176B66]";

const PRIMARY =
  "rounded-lg bg-[#176B66] px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#125650]";

function newMember(): Member {
  return {
    id: crypto.randomUUID(),
    name: "",
    registration: "",
    email: "",
  };
}

function Logo() {
  return (
    <div className="flex items-center gap-2">
      <svg
        aria-hidden="true"
        className="h-9 w-10 text-[#176B66]"
        viewBox="0 0 56 40"
        fill="none"
      >
        <path
          d="m4 14 24-10 24 10-24 10L4 14Z"
          fill="currentColor"
        />
        <path
          d="M15 20v8c5 5 21 5 26 0v-8M49 16v11"
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
        />
        <circle
          cx="49"
          cy="30"
          r="3"
          fill="#E4EEE7"
          stroke="currentColor"
          strokeWidth="2"
        />
      </svg>
      <span className="text-xl font-bold tracking-tight">FYPHub</span>
    </div>
  );
}

type FieldProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: "text" | "email";
  autoComplete?: string;
};

function Field({
  label,
  value,
  onChange,
  type = "text",
  autoComplete,
}: FieldProps) {
  const id = useId();

  return (
    <div className="grid gap-2">
      <label htmlFor={id} className="text-sm font-semibold">
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        autoComplete={autoComplete}
        className={INPUT}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}

function PasswordField({
  label,
  value,
  onChange,
  autoComplete = "new-password",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  autoComplete?: string;
}) {
  const id = useId();
  const [visible, setVisible] = useState(false);

  return (
    <div className="grid gap-2">
      <label htmlFor={id} className="text-sm font-semibold">
        {label}
      </label>

      <div className="relative">
        <input
          id={id}
          className={`${INPUT} pr-16`}
          type={visible ? "text" : "password"}
          value={value}
          autoComplete={autoComplete}
          onChange={(event) => onChange(event.target.value)}
        />
        <button
          type="button"
          aria-controls={id}
          aria-pressed={visible}
          aria-label={`${visible ? "Hide" : "Show"} ${label.toLowerCase()}`}
          onClick={() => setVisible((current) => !current)}
          className="absolute inset-y-0 right-3 text-xs font-semibold text-[#176B66]"
        >
          {visible ? "Hide" : "Show"}
        </button>
      </div>
    </div>
  );
}

function StepProgress({ step }: { step: number }) {
  return (
    <div className="mb-7">
      <div className="relative mx-auto max-w-[280px]">
        <div
          aria-hidden="true"
          className="absolute left-[16.666%] right-[16.666%] top-4 h-[2px] overflow-hidden bg-[#d8e2dc]"
        >
          <div
            className="h-full bg-[#176B66] transition-[width] duration-300 ease-in-out motion-reduce:transition-none"
            style={{ width: `${((step - 1) / 2) * 100}%` }}
          />
        </div>

        <ol
          aria-label="Registration progress"
          className="relative grid grid-cols-3"
        >
          {STEPS.map((label, index) => {
            const number = index + 1;
            const current = number === step;
            const completed = number < step;

            return (
              <li
                key={label}
                aria-current={current ? "step" : undefined}
                className="flex justify-center"
              >
                <span
                  aria-hidden="true"
                  className={[
                    "flex h-8 w-8 items-center justify-center",
                    "rounded-full border text-xs font-bold",
                    "transition-colors duration-300",
                    "motion-reduce:transition-none",
                    current
                      ? "border-[#176B66] bg-[#176B66] text-white"
                      : completed
                        ? "border-[#176B66] bg-[#E4EEE7] text-[#176B66]"
                        : "border-[#c5d1ca] bg-white text-[#64766d]",
                  ].join(" ")}
                >
                  {completed ? (
                    <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4">
                      <path
                        d="m5 12 4 4 10-10"
                        stroke="currentColor"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  ) : (
                    number
                  )}
                </span>
                <span className="sr-only">
                  Step {number}: {label}
                  {completed ? ", completed" : ""}
                </span>
              </li>
            );
          })}
        </ol>
      </div>

      <h2 className="mt-5 text-center text-xl font-bold">
        {STEPS[step - 1]}
      </h2>
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState<"in" | "up">("up");
  const [step, setStep] = useState(1);
  const [error, setError] = useState("");

  const [account, setAccount] = useState<Details>({
    name: "",
    registration: "",
    email: "",
  });

  const [login, setLogin] = useState({
    email: "",
    password: "",
    confirm: "",
  });

  const [members, setMembers] = useState<Member[]>(() => [
    newMember(),
    newMember(),
  ]);

  const [signIn, setSignIn] = useState({
    email: "",
    password: "",
  });

  function changePage(value: "in" | "up") {
    setPage(value);
    setError("");
  }

  function nextStep() {
    let message = "";

    if (step === 1) {
      if (!account.name.trim() || !account.registration.trim()) {
        message = "Enter your full name and registration number.";
      } else if (!EMAIL.test(account.email.trim())) {
        message = "Enter a valid university email.";
      }
    }

    if (step === 2) {
      if (!EMAIL.test(login.email.trim())) {
        message = "Enter a valid shared login email.";
      } else if (
        login.password.length < 8 ||
        login.password.length > 128
      ) {
        message = "Password must contain 8–128 characters.";
      } else if (login.password !== login.confirm) {
        message = "Passwords do not match.";
      }
    }

    setError(message);

    if (!message) {
      setStep((current) => Math.min(3, current + 1));
    }
  }

  function updateMember(
    id: string,
    field: keyof Details,
    value: string,
  ) {
    setMembers((current) =>
      current.map((member) =>
        member.id === id ? { ...member, [field]: value } : member,
      ),
    );
  }

  return (
    <main className="min-h-screen bg-[#F7F5EF] px-4 py-6 text-[#243746] sm:py-8">
      <div className="mx-auto max-w-[640px]">
        <header className="mb-7 flex items-center justify-between gap-3">
          <Logo />

          <nav aria-label="Account navigation" className="flex gap-1">
            {(["in", "up"] as const).map((value) => (
              <button
                key={value}
                type="button"
                aria-current={page === value ? "page" : undefined}
                onClick={() => changePage(value)}
                className={[
                  "rounded-lg px-3 py-2 text-sm font-semibold",
                  page === value
                    ? "bg-[#E4EEE7] text-[#176B66]"
                    : "text-[#4f6470] hover:text-[#176B66]",
                ].join(" ")}
              >
                {value === "in" ? "Sign In" : "Sign Up"}
              </button>
            ))}
          </nav>
        </header>

        <section className="rounded-2xl border border-[#dce4de] bg-white p-5 shadow-[0_8px_30px_rgba(36,55,70,0.04)] sm:p-8">
          {page === "in" ? (
            <>
              <h1 className="mb-7 text-center text-2xl font-bold">
                Sign In
              </h1>

              <div className="space-y-5">
                <Field
                  label="Shared login email"
                  type="email"
                  autoComplete="username"
                  value={signIn.email}
                  onChange={(email) =>
                    setSignIn({ ...signIn, email })
                  }
                />

                <PasswordField
                  label="Password"
                  autoComplete="current-password"
                  value={signIn.password}
                  onChange={(password) =>
                    setSignIn({ ...signIn, password })
                  }
                />

                <button
                  type="button"
                  disabled
                  className="w-full cursor-not-allowed rounded-lg bg-[#cddfd3] py-3 text-sm font-semibold text-[#4f6470]"
                >
                  Sign In
                </button>

                <p className="text-center text-sm text-[#4f6470]">
                  Need a team account?{" "}
                  <button
                    type="button"
                    onClick={() => changePage("up")}
                    className="font-semibold text-[#176B66] underline"
                  >
                    Sign Up
                  </button>
                </p>
              </div>
            </>
          ) : (
            <>
              <h1 className="text-center text-lg font-bold">
                Create Team Account
              </h1>

              <p className="mt-2 mb-6 text-center text-sm text-[#4f6470]">
                Your team will use one email and password.
              </p>

              <StepProgress step={step} />

              {step === 1 && (
                <div className="grid gap-5 sm:grid-cols-2">
                  <div className="sm:col-span-2">
                    <Field
                      label="Full name"
                      autoComplete="name"
                      value={account.name}
                      onChange={(name) =>
                        setAccount({ ...account, name })
                      }
                    />
                  </div>

                  <Field
                    label="Registration number"
                    value={account.registration}
                    onChange={(registration) =>
                      setAccount({ ...account, registration })
                    }
                  />

                  <Field
                    label="University email"
                    type="email"
                    value={account.email}
                    onChange={(email) =>
                      setAccount({ ...account, email })
                    }
                  />
                </div>
              )}

              {step === 2 && (
                <div className="grid gap-5 sm:grid-cols-2">
                  <div className="sm:col-span-2">
                    <Field
                      label="Shared login email"
                      type="email"
                      autoComplete="username"
                      value={login.email}
                      onChange={(email) =>
                        setLogin({ ...login, email })
                      }
                    />
                  </div>

                  <PasswordField
                    label="Password"
                    value={login.password}
                    onChange={(password) =>
                      setLogin({ ...login, password })
                    }
                  />

                  <PasswordField
                    label="Confirm password"
                    value={login.confirm}
                    onChange={(confirm) =>
                      setLogin({ ...login, confirm })
                    }
                  />
                </div>
              )}

              {step === 3 && (
                <div className="space-y-4">
                  <div className="flex justify-end">
                    <button
                      type="button"
                      onClick={() =>
                        setMembers((current) => [
                          ...current,
                          newMember(),
                        ])
                      }
                      className="rounded-lg border border-[#176B66] px-3 py-2 text-sm font-semibold text-[#176B66]"
                    >
                      + Add Member
                    </button>
                  </div>

                  {members.map((member, index) => (
                    <article
                      key={member.id}
                      className="rounded-xl border border-[#dce4de] bg-[#f4f8f5] p-4"
                    >
                      <div className="mb-4 flex items-center justify-between">
                        <h3 className="text-sm font-bold">
                          Member {index + 2}
                        </h3>

                        <button
                          type="button"
                          aria-label={`Remove Member ${index + 2}`}
                          onClick={() =>
                            setMembers((current) =>
                              current.filter(
                                (item) => item.id !== member.id,
                              ),
                            )
                          }
                          className="text-xs font-semibold text-[#176B66] underline"
                        >
                          Remove
                        </button>
                      </div>

                      <div className="grid gap-4 sm:grid-cols-2">
                        <div className="sm:col-span-2">
                          <Field
                            label="Full name"
                            value={member.name}
                            onChange={(value) =>
                              updateMember(member.id, "name", value)
                            }
                          />
                        </div>

                        <Field
                          label="Registration number"
                          value={member.registration}
                          onChange={(value) =>
                            updateMember(
                              member.id,
                              "registration",
                              value,
                            )
                          }
                        />

                        <Field
                          label="University email"
                          type="email"
                          value={member.email}
                          onChange={(value) =>
                            updateMember(member.id, "email", value)
                          }
                        />
                      </div>
                    </article>
                  ))}
                </div>
              )}

              {error && (
                <p
                  role="alert"
                  className="mt-5 rounded-lg bg-[#fff3f0] px-3 py-2 text-sm text-[#a43a33]"
                >
                  {error}
                </p>
              )}

              <div className="mt-7 flex items-center justify-between gap-3 border-t border-[#e8ede9] pt-5">
                {step > 1 && (
                  <button
                    type="button"
                    onClick={() => {
                      setError("");
                      setStep((current) => current - 1);
                    }}
                    className="rounded-lg border border-[#cbd6d0] px-5 py-2.5 text-sm font-semibold"
                  >
                    Back
                  </button>
                )}

                {step < 3 ? (
                  <button
                    type="button"
                    onClick={nextStep}
                    className={`${PRIMARY} ml-auto`}
                  >
                    Next →
                  </button>
                ) : (
                  <button
                    type="button"
                    disabled
                    className="ml-auto cursor-not-allowed rounded-lg bg-[#cddfd3] px-5 py-2.5 text-sm font-semibold text-[#4f6470]"
                  >
                    Create Team Account
                  </button>
                )}
              </div>
            </>
          )}
        </section>
      </div>
    </main>
  );
}