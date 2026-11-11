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
    <section className="rounded-2xl border border-[#dce4de] bg-white p-5" aria-labelledby="group-members-heading">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 id="group-members-heading" className="text-lg font-bold text-[#17324d]">Group members</h2>
          <p className="mt-1 text-sm text-[#60716b]">Everyone uses the shared group workspace and credentials.</p>
        </div>
        <span className="rounded-full bg-[#e4eee7] px-3 py-1 text-xs font-bold text-[#176b66]">{members.length} members</span>
      </div>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[560px] text-left text-sm">
          <thead className="border-b border-[#e8ede9] text-xs uppercase tracking-wide text-[#60716b]">
            <tr><th className="px-2 py-2">Name</th><th className="px-2 py-2">Registration</th><th className="px-2 py-2">Email</th><th className="px-2 py-2">Role</th></tr>
          </thead>
          <tbody className="divide-y divide-[#eef2ef]">
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
