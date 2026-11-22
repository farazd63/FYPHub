import { CollaborationChannel } from "../student/modules/StudentCollaborationChannel";
import type { GroupWorkspace } from "./SupervisorGroupDetails";

export function SupervisorDiscussion({ api, data }: { api: string; data: GroupWorkspace }) {
  if (!data.conversation) {
    return <section className="student-collab supervisor-discussion" aria-labelledby="supervisor-discussion-heading">
      <div className="student-collab__heading"><div><h2 id="supervisor-discussion-heading">Collaboration Channel</h2></div></div>
      <p className="student-collab__notice">{data.assignment?.status === "ACTIVE" ? "Your assignment is active, but the discussion channel is not ready yet. Ask an administrator to configure this cycle's year and session." : "Group discussion becomes available after a supervisor is assigned."}</p>
    </section>;
  }

  return <CollaborationChannel className="supervisor-discussion" api={api} role="supervisor" groupId={data.group.id} userId={data.supervisor.id} />;
}
