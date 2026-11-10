/**
 * useProblems — central hook for problem state management.
 *
 * Fetches the problem list from the backend on mount and provides
 * CRUD operations that keep the local state in sync without full
 * refetches where possible.
 */

import { useState, useEffect, useCallback } from 'react';
import { problemsApi } from '../api/client';
import { apiProblemToFrontend, apiArtifactsToFrontend, frontendToApiCreate } from '../api/mappers';
import type { Problem } from '../types/problem';

interface UseProblemsReturn {
  problems: Problem[];
  loading: boolean;
  error: string | null;
  createProblem: (data: Omit<Problem, 'id' | 'slug' | 'status' | 'createdAt' | 'updatedAt'>) => Promise<Problem>;
  deleteProblem: (id: string) => Promise<void>;
  refreshProblems: () => Promise<void>;
  loadProblemArtifacts: (id: string) => Promise<void>;
}

export function useProblems(): UseProblemsReturn {
  const [problems, setProblems] = useState<Problem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProblems = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await problemsApi.list(100, 0);
      setProblems(response.items.map(apiProblemToFrontend));
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load problems';
      setError(msg);
      console.error('[useProblems] fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProblems();
  }, [fetchProblems]);

  const createProblem = useCallback(
    async (data: Omit<Problem, 'id' | 'slug' | 'status' | 'createdAt' | 'updatedAt'>): Promise<Problem> => {
      const payload = frontendToApiCreate(data as Problem);
      const apiProblem = await problemsApi.create(payload);
      const newProblem = apiProblemToFrontend(apiProblem);
      setProblems(prev => [newProblem, ...prev]);
      return newProblem;
    },
    []
  );

  const deleteProblem = useCallback(async (id: string): Promise<void> => {
    await problemsApi.delete(id);
    setProblems(prev => prev.filter(p => p.id !== id));
  }, []);

  const loadProblemArtifacts = useCallback(async (id: string): Promise<void> => {
    try {
      const [apiProb, artifacts] = await Promise.all([
        problemsApi.get(id),
        problemsApi.listArtifacts(id),
      ]);
      const mapped = apiProblemToFrontend(apiProb);
      mapped.artifacts = apiArtifactsToFrontend(artifacts, mapped);
      setProblems(prev => prev.map(p => (p.id === id ? mapped : p)));
    } catch (err) {
      console.warn('[useProblems] loadProblemArtifacts error:', err);
    }
  }, []);

  return {
    problems,
    loading,
    error,
    createProblem,
    deleteProblem,
    refreshProblems: fetchProblems,
    loadProblemArtifacts,
  };
}
