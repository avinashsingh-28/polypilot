import React from 'react';
import { ProblemDifficulty, ProblemStatus } from '../../types/problem';

interface BadgeProps {
  children?: React.ReactNode;
  variant?: 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info';
  difficulty?: ProblemDifficulty;
  status?: ProblemStatus;
  size?: 'sm' | 'md';
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant,
  difficulty,
  status,
  size = 'md'
}) => {
  let finalVariant = variant || 'default';
  let label = children;

  if (difficulty) {
    label = difficulty;
    if (difficulty.includes('800-1100')) finalVariant = 'success';
    else if (difficulty.includes('1100-1400')) finalVariant = 'info';
    else if (difficulty.includes('1400-1600')) finalVariant = 'primary';
    else if (difficulty.includes('1700-2000')) finalVariant = 'warning';
    else finalVariant = 'danger';
  } else if (status) {
    label = status.toUpperCase();
    if (status === 'verified' || status === 'published') finalVariant = 'success';
    else if (status === 'verifying' || status === 'generating') finalVariant = 'warning';
    else if (status === 'failed') finalVariant = 'danger';
    else finalVariant = 'default';
  }

  const colorStyles: Record<string, { bg: string; text: string; border: string }> = {
    default: {
      bg: 'var(--bg-surface-subtle)',
      text: 'var(--text-secondary)',
      border: 'var(--border-subtle)'
    },
    primary: {
      bg: 'var(--brand-primary-subtle)',
      text: 'var(--brand-primary)',
      border: 'var(--brand-border)'
    },
    success: {
      bg: 'var(--success-bg)',
      text: 'var(--success-text)',
      border: 'var(--success-border)'
    },
    warning: {
      bg: 'var(--warning-bg)',
      text: 'var(--warning-text)',
      border: 'var(--warning-border)'
    },
    danger: {
      bg: 'var(--danger-bg)',
      text: 'var(--danger-text)',
      border: 'var(--danger-border)'
    },
    info: {
      bg: 'var(--info-bg)',
      text: 'var(--info-text)',
      border: 'var(--info-border)'
    }
  };

  const styleConfig = colorStyles[finalVariant] || colorStyles.default;
  const padding = size === 'sm' ? '2px 6px' : '3px 8px';
  const fontSize = size === 'sm' ? '11px' : '12px';

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding,
        fontSize,
        fontWeight: 600,
        borderRadius: 'var(--radius-full)',
        backgroundColor: styleConfig.bg,
        color: styleConfig.text,
        border: `1px solid ${styleConfig.border}`,
        lineHeight: 1.2,
        letterSpacing: '0.01em',
        whiteSpace: 'nowrap'
      }}
    >
      {label}
    </span>
  );
};
