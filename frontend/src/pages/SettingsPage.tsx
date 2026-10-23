import React, { useState } from 'react';
import { Settings as SettingsIcon, CheckCircle2, Shield, Terminal, Clock, Cpu } from 'lucide-react';

export const SettingsPage: React.FC = () => {
  const [compilerStandard, setCompilerStandard] = useState<'c++17' | 'c++20'>('c++17');
  const [defaultTimeLimit, setDefaultTimeLimit] = useState(2000);
  const [defaultMemoryLimit, setDefaultMemoryLimit] = useState(256);
  const [savedNotice, setSavedNotice] = useState(false);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setSavedNotice(true);
    setTimeout(() => setSavedNotice(false), 2500);
  };

  return (
    <div style={{ maxWidth: '840px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div>
        <h1 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)' }}>
          Workspace Settings
        </h1>
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Configure default compilation flags, limits, and local developer environment options.
        </p>
      </div>

      {savedNotice && (
        <div
          className="card"
          style={{
            padding: '12px 16px',
            backgroundColor: 'var(--success-bg)',
            borderColor: 'var(--success-border)',
            color: 'var(--success-text)',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '13px'
          }}
        >
          <CheckCircle2 size={16} />
          <span>Preferences updated in local storage!</span>
        </div>
      )}

      <form onSubmit={handleSave} className="card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <h2 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
          C++ Compilation Defaults
        </h2>

        <div className="form-group">
          <label className="form-label">Default C++ Standard</label>
          <select
            className="form-select"
            value={compilerStandard}
            onChange={(e) => setCompilerStandard(e.target.value as 'c++17' | 'c++20')}
          >
            <option value="c++17">C++17 (Strict Codeforces Polygon Standard)</option>
            <option value="c++20">C++20 (Modern Algorithms Standard)</option>
          </select>
          <span className="form-hint">Used for compiling solutions, validators, checkers, and generators.</span>
        </div>

        <div className="form-group">
          <label className="form-label">Compiler Flags</label>
          <input
            type="text"
            className="form-input"
            value="-O3 -std=c++17 -Wall -Wextra -Wshadow"
            readOnly
            style={{ fontFamily: 'var(--font-mono)' }}
          />
          <span className="form-hint">Enforces high optimization and comprehensive warning detection during verification.</span>
        </div>

        <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '16px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <h2 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
            Default Resource Limits
          </h2>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div className="form-group">
              <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Clock size={12} />
                <span>Default Time Limit (ms)</span>
              </label>
              <input
                type="number"
                className="form-input"
                value={defaultTimeLimit}
                onChange={(e) => setDefaultTimeLimit(Number(e.target.value))}
                min={250}
                max={10000}
                step={250}
              />
            </div>

            <div className="form-group">
              <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Cpu size={12} />
                <span>Default Memory Limit (MB)</span>
              </label>
              <input
                type="number"
                className="form-input"
                value={defaultMemoryLimit}
                onChange={(e) => setDefaultMemoryLimit(Number(e.target.value))}
                min={64}
                max={1024}
                step={64}
              />
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', borderTop: '1px solid var(--border-subtle)', paddingTop: '16px' }}>
          <button type="submit" className="btn btn-primary" style={{ padding: '8px 18px' }}>
            <span>Save Preferences</span>
          </button>
        </div>
      </form>
    </div>
  );
};
