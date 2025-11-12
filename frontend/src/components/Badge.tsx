import React from 'react';

interface BadgeProps {
  severity: 'info' | 'warn' | 'error';
  children: React.ReactNode;
}

export default function Badge({ severity, children }: BadgeProps) {
  const colors = {
    info: 'bg-blue-100 text-blue-800 border-blue-200',
    warn: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    error: 'bg-red-100 text-red-800 border-red-200',
  };

  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${colors[severity]}`}
    >
      {children}
    </span>
  );
}

