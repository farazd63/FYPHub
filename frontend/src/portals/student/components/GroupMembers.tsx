type GroupMember = {
  id: number;
  full_name: string;
  registration_number: string;
  email: string | null;
  designation?: string;
  is_active?: boolean;
};


export function GroupMembers({ members }: { members: GroupMember[] }) {
  if (!members.length) return null;
  return (
    <section className="min-w-0 rounded-2xl border border-fy-border bg-fy-surface p-5" aria-labelledby="group-members-heading">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 id="group-members-heading" className="text-lg font-bold text-fy-text">Group members</h2>
          <p className="mt-1 text-sm text-fy-text-secondary">Everyone uses the shared group workspace and credentials.</p>
        </div>
        <span className="rounded-full bg-fy-success-soft px-3 py-1 text-xs font-bold text-fy-success">{members.length} members</span>
      </div>
      <div className="mt-4 min-w-0 overflow-x-auto">
        <table className="w-full min-w-[560px] text-left text-sm">
          <thead className="border-b border-fy-border text-xs uppercase tracking-wide text-fy-text-secondary">
            <tr><th className="px-2 py-2">Name</th><th className="px-2 py-2">Registration</th><th className="px-2 py-2">Email</th><th className="px-2 py-2">Role</th></tr>
          </thead>
          <tbody className="divide-y divide-fy-border">
            {members.map((member) => (
              <tr key={member.id}>
                <td className="px-2 py-3 font-semibold">{member.full_name}</td>
                <td className="px-2 py-3">{member.registration_number}</td>
                <td className="px-2 py-3">{member.email || "—"}</td>
                <td className="px-2 py-3">{member.designation === "LEADER" ? "Leader" : "Member"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}