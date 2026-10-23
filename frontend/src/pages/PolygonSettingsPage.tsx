import React, { useState } from 'react';
import { Globe2, Key, Eye, EyeOff, ShieldCheck, ExternalLink, AlertCircle, Info } from 'lucide-react';
import { Modal } from '../components/common/Modal';

export const PolygonSettingsPage: React.FC = () => {
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [showSecret, setShowSecret] = useState(false);
  const [apiUrl, setApiUrl] = useState('https://polygon.codeforces.com/api');
  const [showTestModal, setShowTestModal] = useState(false);

  return (
    <div style={{ maxWidth: '880px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)' }}>
          Codeforces Polygon Integration
        </h1>
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Configure official Polygon API credentials to enable automated package creation, file synchronization, revision commits, and package builds.
        </p>
      </div>

      {/* Security Disclaimer Banner */}
      <div
        className="card"
        style={{
          padding: '16px 20px',
          backgroundColor: 'var(--bg-surface)',
          borderLeft: '4px solid var(--info-text)',
          display: 'flex',
          alignItems: 'flex-start',
          gap: '12px'
        }}
      >
        <ShieldCheck size={20} style={{ color: 'var(--info-text)', flexShrink: 0, marginTop: '2px' }} />
        <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          <strong style={{ color: 'var(--text-primary)' }}>Official API Specification:</strong>
          <br />
          PolyPilot strictly conforms to Polygon's official SHA-512 request signing standard. In Phase 1, credentials are not stored or transmitted. In Phase 5, your key and secret will be stored locally with encryption and used solely for authorized Polygon API operations.
        </div>
      </div>

      {/* Configuration Form Card */}
      <div className="card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)' }}>
          Polygon API Credentials
        </h2>

        <div className="form-group">
          <label className="form-label">Polygon API Key</label>
          <input
            type="text"
            className="form-input"
            placeholder="e.g. 0123456789abcdef0123456789abcdef01234567"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            style={{ fontFamily: 'var(--font-mono)' }}
          />
          <span className="form-hint">Obtained from Polygon Settings &gt; API keys</span>
        </div>

        <div className="form-group">
          <label className="form-label">Polygon API Secret</label>
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <input
              type={showSecret ? 'text' : 'password'}
              className="form-input"
              placeholder="e.g. fedcba9876543210fedcba9876543210fedcba98"
              value={apiSecret}
              onChange={(e) => setApiSecret(e.target.value)}
              style={{ paddingRight: '36px', fontFamily: showSecret ? 'var(--font-mono)' : 'inherit' }}
            />
            <button
              type="button"
              onClick={() => setShowSecret(!showSecret)}
              className="btn btn-ghost"
              style={{ position: 'absolute', right: '6px', padding: '4px' }}
              title={showSecret ? 'Hide secret' : 'Show secret'}
            >
              {showSecret ? <EyeOff size={14} /> : <Eye size={14} />}
            </button>
          </div>
          <span className="form-hint">Your private secret used to compute SHA-512 signatures</span>
        </div>

        <div className="form-group">
          <label className="form-label">Polygon Endpoint URL</label>
          <input
            type="text"
            className="form-input"
            value={apiUrl}
            onChange={(e) => setApiUrl(e.target.value)}
            style={{ fontFamily: 'var(--font-mono)' }}
          />
          <span className="form-hint">Default: https://polygon.codeforces.com/api</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid var(--border-subtle)', paddingTop: '16px' }}>
          <a
            href="https://polygon.codeforces.com/docs/api"
            target="_blank"
            rel="noreferrer"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '12px' }}
          >
            <span>Polygon API Documentation</span>
            <ExternalLink size={12} />
          </a>

          <button
            type="button"
            onClick={() => setShowTestModal(true)}
            className="btn btn-secondary"
            style={{ padding: '8px 16px' }}
          >
            <Globe2 size={15} style={{ color: 'var(--info-text)' }} />
            <span>Test Polygon Connection</span>
          </button>
        </div>
      </div>

      {/* Guide Box */}
      <div className="card" style={{ padding: '20px', backgroundColor: 'var(--bg-surface-subtle)' }}>
        <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Info size={15} style={{ color: 'var(--brand-primary)' }} />
          <span>How to Generate Polygon API Keys</span>
        </h3>
        <ol style={{ paddingLeft: '20px', fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6, display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <li>Log in to your account at <a href="https://polygon.codeforces.com" target="_blank" rel="noreferrer">polygon.codeforces.com</a>.</li>
          <li>Click on <strong>Settings</strong> in the top-right navigation menu.</li>
          <li>Navigate to the <strong>API keys</strong> tab.</li>
          <li>Generate a new key pair and copy both the <strong>Key</strong> and <strong>Secret</strong> into this form.</li>
        </ol>
      </div>

      {/* Connection Test Modal */}
      <Modal
        isOpen={showTestModal}
        onClose={() => setShowTestModal(false)}
        title="Polygon API Connectivity"
        subtitle="Phase 5 Integration Pipeline"
        footer={
          <button onClick={() => setShowTestModal(false)} className="btn btn-secondary">
            Close
          </button>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--info-text)', fontWeight: 600 }}>
            <AlertCircle size={18} />
            <span>Polygon Client Integration (Phase 5)</span>
          </div>
          <p>
            In Phase 1, UI credential fields are initialized without saving or transmitting secrets to remote servers.
          </p>
          <p>
            In <strong>Phase 5</strong>, PolyPilot will test this connection using the <code>problems.list</code> API endpoint signed with SHA-512, ensuring valid account authorization before publishing problems or triggering package builds.
          </p>
        </div>
      </Modal>
    </div>
  );
};
