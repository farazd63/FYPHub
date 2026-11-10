import { ArchiveManagementV2 } from "../supervisor-requests/ArchiveManagementV2";
import { OldProjectArchiveImport } from "./OldProjectArchiveImport";

export function ArchiveManagement({ api }: { api: string }) {
  return <><OldProjectArchiveImport api={api} /><ArchiveManagementV2 api={api} /></>;
}
