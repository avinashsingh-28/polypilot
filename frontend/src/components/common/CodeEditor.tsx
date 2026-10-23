import React, { useState } from 'react';
import Editor from '@monaco-editor/react';
import { Copy, Check, Code2 } from 'lucide-react';

interface CodeEditorProps {
  value: string;
  language?: string;
  readOnly?: boolean;
  height?: string | number;
  filename?: string;
  onChange?: (val: string | undefined) => void;
}

export const CodeEditor: React.FC<CodeEditorProps> = ({
  value,
  language = 'cpp',
  readOnly = false,
  height = '420px',
  filename,
  onChange
}) => {
  const [copied, setCopied] = useState(false);
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';

  const handleCopy = () => {
    navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--border-default)',
        overflow: 'hidden',
        backgroundColor: 'var(--bg-surface)'
      }}
    >
      {/* Editor Header Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '6px 12px',
          backgroundColor: 'var(--bg-surface-subtle)',
          borderBottom: '1px solid var(--border-subtle)',
          fontSize: '12px',
          color: 'var(--text-secondary)'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Code2 size={14} style={{ color: 'var(--brand-primary)' }} />
          <span style={{ fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
            {filename || `untitled.${language}`}
          </span>
          {readOnly && (
            <span
              style={{
                fontSize: '10px',
                padding: '1px 6px',
                borderRadius: 'var(--radius-xs)',
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-subtle)',
                color: 'var(--text-muted)'
              }}
            >
              READ-ONLY
            </span>
          )}
        </div>

        <button
          onClick={handleCopy}
          className="btn btn-ghost"
          style={{ padding: '3px 8px', fontSize: '11px', height: '24px' }}
          title="Copy code"
        >
          {copied ? (
            <>
              <Check size={12} style={{ color: 'var(--success-text)' }} />
              <span style={{ color: 'var(--success-text)' }}>Copied</span>
            </>
          ) : (
            <>
              <Copy size={12} />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>

      {/* Monaco Container */}
      <div style={{ height }}>
        <Editor
          height="100%"
          language={language}
          value={value}
          theme={isDark ? 'vs-dark' : 'light'}
          options={{
            readOnly,
            minimap: { enabled: false },
            fontSize: 13,
            fontFamily: "var(--font-mono)",
            lineNumbers: 'on',
            scrollBeyondLastLine: false,
            automaticLayout: true,
            tabSize: 4,
            padding: { top: 8, bottom: 8 }
          }}
          onChange={onChange}
          loading={
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', fontSize: '13px' }}>
              Loading Code Editor...
            </div>
          }
        />
      </div>
    </div>
  );
};
