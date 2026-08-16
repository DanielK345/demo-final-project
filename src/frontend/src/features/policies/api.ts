import { fetchApi } from "@/app/config/api";

export const CURRENT_POLICY_VERSION = "2026-08-16";

export interface PolicyDocument {
  slug: string;
  title: string;
  source_effective_date: string | null;
}

export interface OperationalRule {
  id: string;
  category: string;
  title: string;
  content: string;
  citation: string;
}

export interface PolicyCatalog {
  catalog_version: string;
  approved_at: string;
  effective_from: string;
  status: string;
  approved_by: string;
  target_product: string;
  jurisdiction: string;
  language: string;
  source_sha256: string;
  source_attribution: string;
  legal_notice: string;
  documents: PolicyDocument[];
  operational_rules: OperationalRule[];
  source_endpoint: string;
}

export interface PolicySource {
  catalog_version: string;
  sha256: string;
  attribution: string;
  legal_notice: string;
  content: string;
}

export function getCurrentPolicy(): Promise<PolicyCatalog> {
  return fetchApi<PolicyCatalog>("/api/v1/policies/current");
}

export function getCurrentPolicySource(): Promise<PolicySource> {
  return fetchApi<PolicySource>("/api/v1/policies/current/source");
}
