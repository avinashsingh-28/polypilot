import React from 'react';

interface LogoProps {
  size?: number;
  showText?: boolean;
  className?: string;
}

export const Logo: React.FC<LogoProps> = ({ size = 26, showText = true, className = '' }) => {
  return (
    <div 
      className={`polypilot-logo ${className}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '9px',
        fontWeight: 700,
        letterSpacing: '-0.02em',
        userSelect: 'none',
        color: 'var(--text-primary)'
      }}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 32 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{ flexShrink: 0 }}
      >
        {/* Background polygon shield */}
        <polygon
          points="16,2 30,9 30,23 16,30 2,23 2,9"
          fill="url(#polyGradient)"
          stroke="var(--brand-primary)"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
        {/* Internal geometric pilot facet lines */}
        <path
          d="M16 2 L16 30 M2 9 L30 23 M2 23 L30 9"
          stroke="rgba(255, 255, 255, 0.25)"
          strokeWidth="1"
          strokeDasharray="2 2"
        />
        {/* Navigational pilot core compass / chevron */}
        <path
          d="M16 8 L23 21 L16 17 L9 21 Z"
          fill="#FFFFFF"
          stroke="var(--brand-primary-hover)"
          strokeWidth="1.2"
          strokeLinejoin="round"
        />
        <defs>
          <linearGradient id="polyGradient" x1="2" y1="2" x2="30" y2="30" gradientUnits="userSpaceOnUse">
            <stop stopColor="#4F46E5" />
            <stop offset="1" stopColor="#312E81" />
          </linearGradient>
        </defs>
      </svg>
      {showText && (
        <span style={{ fontSize: size * 0.72, display: 'flex', alignItems: 'center', gap: '4px' }}>
          <span>Poly</span>
          <span style={{ color: 'var(--brand-primary)' }}>Pilot</span>
        </span>
      )}
    </div>
  );
};
