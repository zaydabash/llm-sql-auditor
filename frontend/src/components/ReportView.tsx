import Badge from './Badge';
import QueryCard from './QueryCard';
import { AuditResponse } from '../api';

interface ReportViewProps {
  report: AuditResponse;
}

export default function ReportView({ report }: ReportViewProps) {
  const { summary, issues, rewrites, indexes, llmExplain } = report;

  const issuesBySeverity = {
    error: issues.filter((i) => i.severity === 'error'),
    warn: issues.filter((i) => i.severity === 'warn'),
    info: issues.filter((i) => i.severity === 'info'),
  };

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-bold mb-4">Summary</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <div className="text-2xl font-bold text-gray-900">{summary.totalIssues}</div>
            <div className="text-sm text-gray-600">Total Issues</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-red-600">{summary.highSeverity}</div>
            <div className="text-sm text-gray-600">High Severity</div>
          </div>
          <div>
            <div className="text-sm font-semibold text-gray-900">
              {summary.estImprovement || 'N/A'}
            </div>
            <div className="text-sm text-gray-600">Estimated Improvement</div>
          </div>
        </div>
      </div>

      {/* Issues by Severity */}
      {issues.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-xl font-bold">Issues</h2>

          {issuesBySeverity.error.length > 0 && (
            <div>
              <h3 className="text-lg font-semibold text-red-600 mb-2">Errors</h3>
              <div className="space-y-2">
                {issuesBySeverity.error.map((issue, idx) => (
                  <div key={idx} className="bg-white rounded-lg shadow p-4">
                    <div className="flex items-start justify-between mb-2">
                      <Badge severity="error">{issue.code}</Badge>
                      {issue.rule && (
                        <span className="text-xs text-gray-500">{issue.rule}</span>
                      )}
                    </div>
                    <p className="text-sm text-gray-700">{issue.message}</p>
                    {issue.snippet && (
                      <pre className="mt-2 text-xs bg-gray-50 p-2 rounded overflow-x-auto">
                        {issue.snippet}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {issuesBySeverity.warn.length > 0 && (
            <div>
              <h3 className="text-lg font-semibold text-yellow-600 mb-2">Warnings</h3>
              <div className="space-y-2">
                {issuesBySeverity.warn.map((issue, idx) => (
                  <div key={idx} className="bg-white rounded-lg shadow p-4">
                    <div className="flex items-start justify-between mb-2">
                      <Badge severity="warn">{issue.code}</Badge>
                      {issue.rule && (
                        <span className="text-xs text-gray-500">{issue.rule}</span>
                      )}
                    </div>
                    <p className="text-sm text-gray-700">{issue.message}</p>
                    {issue.snippet && (
                      <pre className="mt-2 text-xs bg-gray-50 p-2 rounded overflow-x-auto">
                        {issue.snippet}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {issuesBySeverity.info.length > 0 && (
            <div>
              <h3 className="text-lg font-semibold text-blue-600 mb-2">Info</h3>
              <div className="space-y-2">
                {issuesBySeverity.info.map((issue, idx) => (
                  <div key={idx} className="bg-white rounded-lg shadow p-4">
                    <div className="flex items-start justify-between mb-2">
                      <Badge severity="info">{issue.code}</Badge>
                      {issue.rule && (
                        <span className="text-xs text-gray-500">{issue.rule}</span>
                      )}
                    </div>
                    <p className="text-sm text-gray-700">{issue.message}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Rewrites */}
      {rewrites.length > 0 && (
        <div>
          <h2 className="text-xl font-bold mb-4">Optimized Queries</h2>
          <div className="space-y-4">
            {rewrites.map((rewrite, idx) => (
              <div key={idx} className="bg-white rounded-lg shadow p-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                  <QueryCard title="Original" query={rewrite.original} />
                  <QueryCard title="Optimized" query={rewrite.optimized} />
                </div>
                <div className="mt-4">
                  <h4 className="text-sm font-semibold text-gray-700 mb-2">Rationale</h4>
                  <p className="text-sm text-gray-600">{rewrite.rationale}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Index Suggestions */}
      {indexes.length > 0 && (
        <div>
          <h2 className="text-xl font-bold mb-4">Index Suggestions</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {indexes.map((index, idx) => (
              <div key={idx} className="bg-white rounded-lg shadow p-4">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-semibold text-gray-900">{index.table}</h3>
                  {index.type && (
                    <Badge severity="info">{index.type}</Badge>
                  )}
                </div>
                <div className="mb-2">
                  <span className="text-sm text-gray-600">Columns: </span>
                  <span className="text-sm font-mono text-gray-900">
                    ({index.columns.join(', ')})
                  </span>
                </div>
                <p className="text-sm text-gray-700 mb-2">{index.rationale}</p>
                {index.expected_improvement && (
                  <p className="text-xs text-gray-500">{index.expected_improvement}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* LLM Explanation */}
      {llmExplain && (
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold mb-4">AI Explanation</h2>
          <div className="prose prose-sm max-w-none">
            <pre className="whitespace-pre-wrap text-sm text-gray-700">{llmExplain}</pre>
          </div>
        </div>
      )}
    </div>
  );
}

