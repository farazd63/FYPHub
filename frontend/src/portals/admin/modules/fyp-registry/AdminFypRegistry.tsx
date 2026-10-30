import { FypRegistryPage } from "../../../shared/FypRegistryPage";

export function AdminFypRegistry({ api }: { api: string }) {
  return <FypRegistryPage api={api} scope="admin" title="FYP Registry & Project Monitoring" />;
}
