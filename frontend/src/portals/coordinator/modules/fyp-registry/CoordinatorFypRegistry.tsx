import { FypRegistryPage } from "../../../shared/FypRegistryPage";

export function CoordinatorFypRegistry({ api }: { api: string }) {
  return <FypRegistryPage api={api} scope="coordinator" title="FYP Students & Projects" />;
}
