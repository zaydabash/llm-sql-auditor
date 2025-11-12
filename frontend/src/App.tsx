import { useState } from 'react';
import InputPanel from './components/InputPanel';
import ReportView from './components/ReportView';
import { auditQueries, AuditResponse } from './api';

export default function App() {
  const [report, setReport] = useState<AuditResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (
    schema: string,
    queries: string[],
    dialect: 'postgres' | 'sqlite'
  ) => {
    setLoading(true);
    setError(null);
    setReport(null);

    try {
      const result = await auditQueries({ schema, queries, dialect });
      setReport(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <h1 className="text-3xl font-bold text-gray-900">SQL Auditor</h1>
          <p className="mt-2 text-sm text-gray-600">
            LLM-driven SQL optimization and analysis tool
          </p>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          <div>
            <div className="bg-white rounded-lg shadow p-6 sticky top-8">
              <h2 className="text-xl font-bold mb-4">Input</h2>
              <InputPanel onSubmit={handleSubmit} loading={loading} />
              {error && (
                <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-md">
                  <p className="text-sm text-red-800">{error}</p>
                </div>
              )}
            </div>
          </div>

          <div>
            {report ? (
              <ReportView report={report} />
            ) : (
              <div className="bg-white rounded-lg shadow p-12 text-center">
                <p className="text-gray-500">
                  Enter your schema and queries to get started
                </p>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

