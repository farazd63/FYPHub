import { AdminArchiveProjects } from "./AdminArchiveProjects";

export function ArchiveManagement({ api }: { api: string }) {
  return <AdminArchiveProjects api={api} />;
}
