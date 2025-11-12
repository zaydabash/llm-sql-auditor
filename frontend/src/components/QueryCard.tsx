interface QueryCardProps {
  title: string;
  query: string;
}

export default function QueryCard({ title, query }: QueryCardProps) {
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-2">{title}</h3>
      <pre className="bg-gray-50 p-3 rounded text-xs overflow-x-auto">
        <code>{query}</code>
      </pre>
    </div>
  );
}

