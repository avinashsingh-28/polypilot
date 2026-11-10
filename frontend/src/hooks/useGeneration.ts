import { useCallback, useEffect, useRef, useState } from 'react';
import { apiClient } from '../api/client';

export interface GenerationStepLog {
  step: number;
  key: string;
  name: string;
  status: 'running' | 'completed' | 'failed' | 'pending';
  timestamp: string;
  error?: string;
}

export interface GenerationStatus {
  jobId: string;
  problemId: string;
  status: 'running' | 'completed' | 'failed' | 'pending';
  currentStep: number;
  totalSteps: number;
  currentStepName: string | null;
  stepsLog: GenerationStepLog[];
  errorMessage: string | null;
  startedAt: string | null;
  completedAt: string | null;
}

interface UseGenerationReturn {
  isGenerating: boolean;
  status: GenerationStatus | null;
  error: string | null;
  startGeneration: (problemId: string) => Promise<void>;
  stopPolling: () => void;
}

const POLL_INTERVAL_MS = 2000;

export function useGeneration(onCompleted?: (problemId: string) => void): UseGenerationReturn {
  const [isGenerating, setIsGenerating] = useState(false);
  const [status, setStatus] = useState<GenerationStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const activeProblemId = useRef<string | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const pollStatus = useCallback(async (problemId: string) => {
    try {
      const data = await apiClient<any>(`/problems/${problemId}/generation-status`);
      const mapped: GenerationStatus = {
        jobId: data.job_id,
        problemId: data.problem_id,
        status: data.status,
        currentStep: data.current_step,
        totalSteps: data.total_steps,
        currentStepName: data.current_step_name,
        stepsLog: (data.steps_log || []).map((s: any) => ({
          step: s.step,
          key: s.key,
          name: s.name,
          status: s.status,
          timestamp: s.timestamp,
          error: s.error,
        })),
        errorMessage: data.error_message,
        startedAt: data.started_at,
        completedAt: data.completed_at,
      };
      setStatus(mapped);

      if (data.status === 'completed' || data.status === 'failed') {
        stopPolling();
        setIsGenerating(false);
        if (data.status === 'completed' && onCompleted) {
          onCompleted(problemId);
        }
        if (data.status === 'failed') {
          setError(data.error_message || 'Generation failed.');
        }
      }
    } catch (err) {
      // Swallow poll errors — the interval will retry
      console.warn('Poll error:', err);
    }
  }, [stopPolling, onCompleted]);

  const startGeneration = useCallback(async (problemId: string) => {
    setError(null);
    setStatus(null);
    setIsGenerating(true);
    activeProblemId.current = problemId;

    try {
      await apiClient<any>(`/problems/${problemId}/generate`, {
        method: 'POST',
      });
    } catch (err: any) {
      const msg = err?.message || 'Failed to start generation.';
      setError(msg);
      setIsGenerating(false);
      return;
    }

    // Start polling
    stopPolling();
    pollRef.current = setInterval(() => {
      pollStatus(problemId);
    }, POLL_INTERVAL_MS);

    // Fire immediately
    pollStatus(problemId);
  }, [pollStatus, stopPolling]);

  // Cleanup on unmount
  useEffect(() => {
    return () => { stopPolling(); };
  }, [stopPolling]);

  return { isGenerating, status, error, startGeneration, stopPolling };
}

