import type { ComplianceCheck } from "./adfeed-api";

/** API compliance messages are English — pass through directly. */
export function localizeComplianceCheck(c: ComplianceCheck): string {
  return c.message || c.id;
}
