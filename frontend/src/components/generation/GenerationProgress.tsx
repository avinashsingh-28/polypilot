import React from 'react';
import { CheckCircle2, Loader2, XCircle, Circle, ChevronRight } from 'lucide-react';
import type { GenerationStatus, GenerationStepLog } from '../../hooks/useGeneration';

interface GenerationProgressProps {
  status: GenerationStatus | null;
  isGenerating: boolean;
  error: string | null;
  onDismiss?: () => void;
}

const ALL_STEPS = [
  { key: 'specification',      name: 'Building Specification' },
  { key: 'statement',          name: 'Writing Problem Statement' },
  { key: 'reference_solution', name: 'Generating Reference Solution' },
  { key: 'brute_force',        name: 'Generating Brute-Force Solution' },
  { key: 'validator',          name: 'Writing Testlib Validator' },
  { key: 'generator',          name: 'Writing Test Generator' },
  { key: 'editorial',          name: 'Writing Editorial' },
];

function StepIcon({ stepStatus }: { stepStatus: string }) {
  switch (stepStatus) {
    case 'completed':
      return <CheckCircle2 size={16} style={{ color: 'var(--status-verified)', flexShrink: 0 }} />;
    case 'running':
      return (
        <Loader2
          size={16}
          style={{ color: 'var(--brand-primary)', flexShrink: 0, animation: 'spin 1s linear infinite' }}
        />
      );
    case 'failed':
      return <XCircle size={16} style={{ color: 'var(--status-failed)', flexShrink: 0 }} />;
    default:
      return <Circle size={16} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />;
  }
}

function getStepStatus(key: string, stepsLog: GenerationStepLog[], currentStep: number, stepIndex: number): string {
  const logEntry = stepsLog.find(s => s.key === key);
  if (logEntry) return logEntry.status;
  if (stepIndex + 1 < currentStep) return 'completed';
  if (stepIndex + 1 === currentStep) return 'running';
  return 'pending';
}

export const GenerationProgress: React.FC<GenerationProgressProps> = ({
  status,
  isGenerating,
  error,
  onDismiss,
}) => {
  if (!isGenerating && !status && !error) return null;

  const progress = status ? Math.round((status.currentStep / status.totalSteps) * 100) : 0;
  const isDone = status?.status === 'completed';
  const isFailed = status?.status === 'failed' || !!error;

  return (
    <div
      className="card"
      style={{
        border: isFailed
          ? '1px solid var(--status-failed)'
          : isDone
            ? '1px solid var(--status-verified)'
            : '1px solid var(--brand-primary)',
        padding: '20px',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {isGenerating && !isFailed && (
            <Loader2
              size={18}
              style={{ color: 'var(--brand-primary)', animation: 'spin 1s linear infinite' }}
            />
          )}
          {isDone && <CheckCircle2 size={18} style={{ color: 'var(--status-verified)' }} />}
          {isFailed && <XCircle size={18} style={{ color: 'var(--status-failed)' }} />}
          <span style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text-primary)' }}>
            {isDone
              ? 'Generation Complete'
              : isFailed
                ? 'Generation Failed'
                : status?.currentStepName ?? 'Starting generation…'}
          </span>
        </div>

        {(isDone || isFailed) && onDismiss && (
          <button
            onClick={onDismiss}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontSize: '12px',
              color: 'var(--text-muted)',
              padding: '2px 6px',
              borderRadius: '4px',
            }}
          >
            Dismiss
          </button>
        )}
      </div>

      {/* Progress bar */}
      {!isFailed && (
        <div
          style={{
            height: '4px',
            background: 'var(--border-subtle)',
            borderRadius: '2px',
            marginBottom: '16px',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              height: '100%',
              width: `${isDone ? 100 : progress}%`,
              background: isDone ? 'var(--status-verified)' : 'var(--brand-primary)',
              borderRadius: '2px',
              transition: 'width 0.5s ease',
            }}
          />
        </div>
      )}

      {/* Error message */}
      {(error || status?.errorMessage) && (
        <div
          style={{
            background: 'rgba(239,68,68,0.08)',
            border: '1px solid rgba(239,68,68,0.3)',
            borderRadius: '6px',
            padding: '10px 12px',
            marginBottom: '14px',
            fontSize: '12px',
            color: 'var(--status-failed)',
          }}
        >
          {error || status?.errorMessage}
        </div>
      )}

      {/* Steps list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {ALL_STEPS.map((step, idx) => {
          const stepStatus = status
            ? getStepStatus(step.key, status.stepsLog, status.currentStep, idx)
            : 'pending';

          const logEntry = status?.stepsLog.find(s => s.key === step.key);

          return (
            <div
              key={step.key}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                padding: '6px 8px',
                borderRadius: '6px',
                background:
                  stepStatus === 'running'
                    ? 'rgba(99,102,241,0.06)'
                    : 'transparent',
                opacity: stepStatus === 'pending' ? 0.5 : 1,
                transition: 'all 0.2s',
              }}
            >
              <StepIcon stepStatus={stepStatus} />
              <span
                style={{
                  fontSize: '13px',
                  color: stepStatus === 'completed'
                    ? 'var(--text-secondary)'
                    : 'var(--text-primary)',
                  flex: 1,
                }}
              >
                {step.name}
              </span>
              {stepStatus === 'completed' && (
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Done</span>
              )}
              {stepStatus === 'failed' && logEntry?.error && (
                <span
                  style={{
                    fontSize: '11px',
                    color: 'var(--status-failed)',
                    maxWidth: '200px',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                  title={logEntry.error}
                >
                  {logEntry.error}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Footer */}
      {isDone && (
        <div
          style={{
            marginTop: '14px',
            paddingTop: '12px',
            borderTop: '1px solid var(--border-subtle)',
            fontSize: '12px',
            color: 'var(--text-secondary)',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
          }}
        >
          <CheckCircle2 size={13} style={{ color: 'var(--status-verified)' }} />
          All 7 artifacts generated and saved. Navigate to the Problem Workspace to review.
        </div>
      )}
    </div>
  );
};

