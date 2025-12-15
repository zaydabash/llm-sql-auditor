import React, { useState } from 'react';

interface InputPanelProps {
  onSubmit: (schema: string, queries: string[], dialect: 'postgres' | 'sqlite') => void;
  loading: boolean;
}

export default function InputPanel({ onSubmit, loading }: InputPanelProps) {
  const [schema, setSchema] = useState('');
  const [queries, setQueries] = useState('');
  const [dialect, setDialect] = useState<'postgres' | 'sqlite'>('postgres');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validate schema
    if (!schema.trim()) {
      alert('Please enter a schema DDL');
      return;
    }

    // Parse queries
    const queryList = queries
      .split('---')
      .map((q) => q.trim())
      .filter((q) => q.length > 0);
    
    if (queryList.length === 0) {
      alert('Please enter at least one query');
      return;
    }

    try {
      onSubmit(schema, queryList, dialect);
    } catch (error) {
      console.error('Submit error:', error);
      alert('Error submitting form. Please check your input.');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="dialect" className="block text-sm font-medium text-gray-700 mb-2">
          SQL Dialect
        </label>
        <select
          id="dialect"
          value={dialect}
          onChange={(e) => setDialect(e.target.value as 'postgres' | 'sqlite')}
          className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="postgres">PostgreSQL</option>
          <option value="sqlite">SQLite</option>
        </select>
      </div>

      <div>
        <label htmlFor="schema" className="block text-sm font-medium text-gray-700 mb-2">
          Schema DDL
        </label>
        <textarea
          id="schema"
          value={schema}
          onChange={(e) => setSchema(e.target.value)}
          placeholder="CREATE TABLE users (...);&#10;-- @rows=50000&#10;CREATE TABLE orders (...);"
          rows={8}
          className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <div>
        <label htmlFor="queries" className="block text-sm font-medium text-gray-700 mb-2">
          SQL Queries (separate multiple queries with ---)
        </label>
        <textarea
          id="queries"
          value={queries}
          onChange={(e) => setQueries(e.target.value)}
          placeholder="SELECT * FROM orders;&#10;&#10;---&#10;&#10;SELECT * FROM users WHERE LOWER(email) = 'test@example.com';"
          rows={8}
          className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <button
        type="submit"
        disabled={loading}
        className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? 'Analyzing...' : 'Analyze Queries'}
      </button>
    </form>
  );
}

