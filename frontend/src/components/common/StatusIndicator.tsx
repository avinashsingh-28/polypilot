import React from 'react';

interface StatusIndicatorProps {
  status: 'online' | 'busy' | 'offline' | 'error';
  pulse?: boolean;
  label?: string;
}

export const StatusIndicator: React.FC<StatusIndicatorProps> = ({
  status,
  pulse = false,
  label
}) => {
  const colors = {
    online: 'var(--success-text)',
    busy: 'var(--warning-text)',
    offline: 'var(--text-muted)',
    error: 'var(--danger-text)'
  };

  const currentColor = colors[status] || colors.offline;

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          backgroundColor: currentColor,
          display: 'inline-block',
          boxShadow: pulse ? `0 0 0 2px ${currentColor}33` : 'none',
          animation: pulse ? 'pulse 1.8s infinite' : 'none'
        }}
      />
      {label && (
        <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
          {label}
        </span>
      )}
    </div>
  );
};
