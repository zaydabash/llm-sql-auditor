export interface AuditRequest {
  schema: string;
  queries: string[];
  dialect: 'postgres' | 'sqlite';
}

export interface Issue {
  code: string;
  severity: 'info' | 'warn' | 'error';
  message: string;
  snippet?: string;
  line?: number;
  rule?: string;
  query_index?: number;
}

export interface Rewrite {
  original: string;
  optimized: string;
  rationale: string;
  query_index?: number;
}

export interface IndexSuggestion {
  table: string;
  columns: string[];
  type?: string;
  rationale: string;
  expected_improvement?: string;
}

export interface Summary {
  totalIssues: number;
  highSeverity: number;
  estImprovement?: string;
}

export interface AuditResponse {
  summary: Summary;
  issues: Issue[];
  rewrites: Rewrite[];
  indexes: IndexSuggestion[];
  llmExplain: string;
}

export async function auditQueries(request: AuditRequest): Promise<AuditResponse> {
  const response = await fetch('/api/audit', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to audit queries');
  }

  return response.json();
}

