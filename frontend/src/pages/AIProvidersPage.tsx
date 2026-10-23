import React, { useState } from 'react';
import { 
  Sparkles, 
  Key, 
  Eye, 
  EyeOff, 
  CheckCircle2, 
  AlertCircle, 
  ShieldCheck, 
  ExternalLink,
  Cpu
} from 'lucide-react';
import { INITIAL_AI_PROVIDERS } from '../data/mockData';
import { AIProviderConfig } from '../types/settings';
import { Modal } from '../components/common/Modal';

export const AIProvidersPage: React.FC = () => {
  const [providers, setProviders] = useState<AIProviderConfig[]>(INITIAL_AI_PROVIDERS);
  const [showKeyMap, setShowKeyMap] = useState<Record<string, boolean>>({});
  const [testModalProvider, setTestModalProvider] = useState<string | null>(null);

  const toggleShowKey = (providerId: string) => {
    setShowKeyMap(prev => ({ ...prev, [providerId]: !prev[providerId] }));
  };

  const handleKeyChange = (providerId: string, value: string) => {
    setProviders(prev =>
      prev.map(p => (p.id === providerId ? { ...p, apiKey: value } : p))
    );
  };

  const handleModelChange = (providerId: string, modelId: string) => {
    setProviders(prev =>
      prev.map(p => (p.id === providerId ? { ...p, selectedModel: modelId } : p))
    );
  };

  return (
    <div style={{ maxWidth: '960px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)' }}>
          AI Providers & Bring Your Own Key (BYOK)
        </h1>
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Connect your preferred AI model provider for problem specification generation and automated repair loops.
        </p>
      </div>

      {/* Security Banner */}
      <div
        className="card"
        style={{
          padding: '16px 20px',
          backgroundColor: 'var(--bg-surface)',
          borderLeft: '4px solid var(--brand-primary)',
          display: 'flex',
          alignItems: 'flex-start',
          gap: '12px'
        }}
      >
        <ShieldCheck size={20} style={{ color: 'var(--brand-primary)', flexShrink: 0, marginTop: '2px' }} />
        <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          <strong style={{ color: 'var(--text-primary)' }}>Zero-Knowledge Local Secret Architecture:</strong>
          <br />
          PolyPilot treats all provider API keys and Polygon credentials as strict secrets. Keys are never bundled into client-side JS or exposed in browser logs. In Phase 2, keys will be persisted with machine-bound Fernet symmetric encryption on your local backend.
        </div>
      </div>

      {/* Providers Grid */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {providers.map((provider) => {
          const isKeyVisible = Boolean(showKeyMap[provider.id]);

          return (
            <div
              key={provider.id}
              className="card"
              style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {provider.name}
                    </h3>
                    {provider.id === 'gemini' && (
                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: 600,
                          padding: '1px 8px',
                          borderRadius: 'var(--radius-full)',
                          backgroundColor: 'var(--brand-primary-subtle)',
                          color: 'var(--brand-primary)',
                          border: '1px solid var(--brand-border)'
                        }}
                      >
                        Recommended for CP
                      </span>
                    )}
                  </div>
                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                    {provider.description}
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => setTestModalProvider(provider.name)}
                  className="btn btn-secondary"
                  style={{ fontSize: '12px' }}
                >
                  <Sparkles size={13} style={{ color: 'var(--brand-primary)' }} />
                  <span>Test Connectivity</span>
                </button>
              </div>

              {/* Configuration Inputs */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px' }}>
                {/* Model Selector */}
                <div className="form-group">
                  <label className="form-label">Selected Model</label>
                  <select
                    className="form-select"
                    value={provider.selectedModel}
                    onChange={(e) => handleModelChange(provider.id, e.target.value)}
                  >
                    {provider.models.map((model) => (
                      <option key={model.id} value={model.id}>
                        {model.name} ({model.contextWindow}) {model.recommended ? '★' : ''}
                      </option>
                    ))}
                  </select>
                </div>

                {/* API Key Input */}
                <div className="form-group">
                  <label className="form-label">
                    {provider.id === 'ollama' ? 'Local Base URL' : 'API Key'}
                  </label>
                  <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                    <input
                      type={isKeyVisible ? 'text' : 'password'}
                      className="form-input"
                      placeholder={provider.id === 'ollama' ? 'http://localhost:11434' : 'Enter your provider API key (e.g. AIza... or sk-...)'}
                      value={provider.id === 'ollama' ? provider.customEndpoint || '' : provider.apiKey}
                      onChange={(e) => handleKeyChange(provider.id, e.target.value)}
                      style={{ paddingRight: '36px', fontFamily: isKeyVisible ? 'var(--font-mono)' : 'inherit' }}
                    />
                    {provider.id !== 'ollama' && (
                      <button
                        type="button"
                        onClick={() => toggleShowKey(provider.id)}
                        className="btn btn-ghost"
                        style={{ position: 'absolute', right: '6px', padding: '4px' }}
                        title={isKeyVisible ? 'Hide key' : 'Show key'}
                      >
                        {isKeyVisible ? <EyeOff size={14} /> : <Eye size={14} />}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Connectivity Test Modal */}
      <Modal
        isOpen={Boolean(testModalProvider)}
        onClose={() => setTestModalProvider(null)}
        title={`${testModalProvider} Connectivity`}
        subtitle="Phase 2 Backend Integration Status"
        footer={
          <button onClick={() => setTestModalProvider(null)} className="btn btn-secondary">
            Close
          </button>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--info-text)', fontWeight: 600 }}>
            <AlertCircle size={18} />
            <span>Secure Backend Verification Pending (Phase 2)</span>
          </div>
          <p>
            In Phase 1, UI credential forms do not collect, transmit, or persist keys across network boundaries.
          </p>
          <p>
            In <strong>Phase 2</strong>, the FastAPI backend will provide a dedicated <code>/api/providers/verify</code> endpoint that validates API authentication, checks quota limits, and executes a test latency benchmark with zero secrets exposed to the browser.
          </p>
        </div>
      </Modal>
    </div>
  );
};
