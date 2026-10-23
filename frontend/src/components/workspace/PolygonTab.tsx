import React from 'react';
import { Globe2, ExternalLink, CheckCircle2, AlertTriangle, UploadCloud, RefreshCw, FileText, Check } from 'lucide-react';
import { Problem } from '../../types/problem';
import { Badge } from '../common/Badge';

interface PolygonTabProps {
  problem: Problem;
}

export const PolygonTab: React.FC<PolygonTabProps> = ({ problem }) => {
  const polygon = problem.polygon;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Sync Card */}
      <div
        className="card"
        style={{
          padding: '24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '16px',
          borderLeft: polygon?.linked ? '4px solid var(--info-text)' : '4px solid var(--border-default)'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div
            style={{
              width: 42,
              height: 42,
              borderRadius: 'var(--radius-md)',
              backgroundColor: polygon?.linked ? 'var(--info-bg)' : 'var(--bg-surface-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: polygon?.linked ? 'var(--info-text)' : 'var(--text-muted)'
            }}
          >
            <Globe2 size={24} />
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)' }}>
                {polygon?.linked ? 'Codeforces Polygon Package Connected' : 'Not Published to Polygon'}
              </h3>
              <Badge variant={polygon?.linked ? 'info' : 'default'}>
                {polygon?.linked ? `REVISION ${polygon.latestRevision}` : 'UNLINKED'}
              </Badge>
            </div>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '3px' }}>
              {polygon?.linked
                ? `Polygon Problem ID: ${polygon.problemId} • Package Build Status: ${polygon.packageBuildStatus.toUpperCase()}`
                : 'Directly publish problem statement, solutions, validator, tests, and build packages via official Polygon SHA-512 API.'}
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          {polygon?.linked && polygon.problemUrl ? (
            <a
              href={polygon.problemUrl}
              target="_blank"
              rel="noreferrer"
              className="btn btn-secondary"
            >
              <span>Open in Polygon</span>
              <ExternalLink size={14} />
            </a>
          ) : (
            <button className="btn btn-primary" disabled title="Polygon publishing executes in Phase 5">
              <UploadCloud size={15} />
              <span>Publish to Polygon (Phase 5)</span>
            </button>
          )}
        </div>
      </div>

      {/* Artifact Sync Checklist */}
      <div className="card" style={{ padding: '20px' }}>
        <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '16px' }}>
          Polygon Package Manifest Checklist
        </h4>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 14px', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-surface-subtle)' }}>
            <CheckCircle2 size={16} style={{ color: 'var(--success-text)' }} />
            <div>
              <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>Statement (LaTeX)</div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>English statement saved with examples</div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 14px', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-surface-subtle)' }}>
            <CheckCircle2 size={16} style={{ color: 'var(--success-text)' }} />
            <div>
              <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>Solutions (main & slow)</div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Uploaded with tag MAIN and ACCEPTED</div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 14px', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-surface-subtle)' }}>
            <CheckCircle2 size={16} style={{ color: 'var(--success-text)' }} />
            <div>
              <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>Validator (testlib.h)</div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Bound checks & test verification active</div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 14px', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-surface-subtle)' }}>
            <CheckCircle2 size={16} style={{ color: 'var(--success-text)' }} />
            <div>
              <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>Test Scripts & Generators</div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Script commands configured with stdin/stdout</div>
            </div>
          </div>
        </div>
      </div>

      {/* Polygon API Details Notice */}
      <div className="card" style={{ padding: '18px 20px', backgroundColor: 'var(--bg-surface-subtle)' }}>
        <h4 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '6px' }}>
          Official Polygon API Method Coverage
        </h4>
        <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          PolyPilot Phase 5 implements the complete official Polygon API standard (<code>problem.saveFile</code>, <code>problem.setValidator</code>, <code>problem.setChecker</code>, <code>problem.saveScript</code>, <code>problem.commit</code>, and <code>problem.buildPackage</code>). Real-time package build polling inspects build cautions and compilation warnings automatically.
        </p>
      </div>
    </div>
  );
};
