import React, { useState } from 'react';
import { 
  Plus, 
  Search, 
  FolderGit2, 
  Clock, 
  Cpu, 
  Globe2, 
  ChevronRight, 
  Trash2,
  Filter
} from 'lucide-react';
import { Problem, ProblemDifficulty, ProblemStatus } from '../types/problem';
import { Badge } from '../components/common/Badge';

interface MyProblemsPageProps {
  problems: Problem[];
  onOpenProblem: (id: string) => void;
  onNavigateNewProblem: () => void;
  onDeleteProblem?: (id: string) => void;
}

export const MyProblemsPage: React.FC<MyProblemsPageProps> = ({
  problems,
  onOpenProblem,
  onNavigateNewProblem,
  onDeleteProblem
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedDifficulty, setSelectedDifficulty] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');

  const filteredProblems = problems.filter((problem) => {
    const matchesSearch = 
      problem.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      problem.shortIdea.toLowerCase().includes(searchQuery.toLowerCase()) ||
      problem.slug.toLowerCase().includes(searchQuery.toLowerCase()) ||
      problem.intendedAlgorithm.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesDiff = selectedDifficulty === 'all' || problem.difficulty === selectedDifficulty;
    const matchesStatus = selectedStatus === 'all' || problem.status === selectedStatus;

    return matchesSearch && matchesDiff && matchesStatus;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)' }}>
            My Problems
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '2px' }}>
            Manage and inspect your problem packages, verification suites, and Polygon states.
          </p>
        </div>

        <button
          onClick={onNavigateNewProblem}
          className="btn btn-primary"
          style={{ padding: '8px 16px', fontWeight: 600 }}
        >
          <Plus size={16} />
          <span>New Problem</span>
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div
        className="card"
        style={{
          padding: '12px 16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px'
        }}
      >
        <div style={{ position: 'relative', flex: 1, minWidth: '240px' }}>
          <Search size={15} style={{ position: 'absolute', left: '12px', top: '10px', color: 'var(--text-muted)' }} />
          <input
            type="text"
            className="form-input"
            style={{ paddingLeft: '34px', fontSize: '13px' }}
            placeholder="Search by title, algorithm, idea, or slug..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Filter size={14} style={{ color: 'var(--text-muted)' }} />
            <select
              className="form-select"
              style={{ width: 'auto', fontSize: '13px', padding: '6px 10px' }}
              value={selectedDifficulty}
              onChange={(e) => setSelectedDifficulty(e.target.value)}
            >
              <option value="all">All Difficulties</option>
              <option value="Div. 2 A (800-1100)">Div. 2 A</option>
              <option value="Div. 2 B (1100-1400)">Div. 2 B</option>
              <option value="Div. 2 C (1400-1600)">Div. 2 C</option>
              <option value="Div. 2 D / Div. 1 B (1700-2000)">Div. 2 D / Div. 1 B</option>
              <option value="Div. 1 C+ (2100+)">Div. 1 C+</option>
            </select>
          </div>

          <select
            className="form-select"
            style={{ width: 'auto', fontSize: '13px', padding: '6px 10px' }}
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
          >
            <option value="all">All Statuses</option>
            <option value="draft">Draft</option>
            <option value="verified">Verified</option>
            <option value="published">Published</option>
          </select>
        </div>
      </div>

      {/* Problems List or Empty State */}
      {filteredProblems.length === 0 ? (
        <div
          className="card"
          style={{
            padding: '60px 24px',
            textAlign: 'center',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '12px'
          }}
        >
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: 'var(--radius-full)',
              backgroundColor: 'var(--bg-surface-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-muted)'
            }}
          >
            <FolderGit2 size={24} />
          </div>
          <div>
            <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
              {problems.length === 0 ? 'No problems found in workspace' : 'No matching problems'}
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px', maxWidth: '360px' }}>
              {problems.length === 0
                ? 'Create a new competitive programming problem or return to the dashboard to load the demonstration problem.'
                : 'Try adjusting your search criteria or filters to locate your problem.'}
            </p>
          </div>
          {problems.length === 0 && (
            <button
              onClick={onNavigateNewProblem}
              className="btn btn-primary"
              style={{ marginTop: '6px' }}
            >
              <Plus size={15} />
              <span>Create Problem</span>
            </button>
          )}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {filteredProblems.map((problem) => (
            <div
              key={problem.id}
              className="card"
              style={{
                padding: '16px 20px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '16px',
                cursor: 'pointer',
                transition: 'border-color 0.15s ease, box-shadow 0.15s ease'
              }}
              onClick={() => onOpenProblem(problem.id)}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--brand-primary)';
                e.currentTarget.style.boxShadow = 'var(--shadow-md)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--border-subtle)';
                e.currentTarget.style.boxShadow = 'var(--shadow-sm)';
              }}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', flex: 1, minWidth: '280px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                  <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {problem.title}
                  </h3>
                  <Badge difficulty={problem.difficulty} size="sm" />
                  <Badge status={problem.status} size="sm" />
                  {problem.polygon?.linked && (
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                        fontSize: '11px',
                        color: 'var(--info-text)',
                        backgroundColor: 'var(--info-bg)',
                        border: '1px solid var(--info-border)',
                        padding: '1px 6px',
                        borderRadius: 'var(--radius-full)'
                      }}
                    >
                      <Globe2 size={11} />
                      <span>Polygon ID: {problem.polygon.problemId}</span>
                    </span>
                  )}
                </div>

                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.4, maxWidth: '780px' }}>
                  {problem.shortIdea}
                </p>

                <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                  <span style={{ fontFamily: 'var(--font-mono)' }}>{problem.slug}</span>
                  <span>•</span>
                  <span>Algorithm: <strong>{problem.intendedAlgorithm}</strong></span>
                  <span>•</span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Clock size={12} />
                    <span>{problem.timeLimitMs}ms</span>
                  </span>
                  <span>•</span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Cpu size={12} />
                    <span>{problem.memoryLimitMb}MB</span>
                  </span>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onOpenProblem(problem.id);
                  }}
                  className="btn btn-secondary"
                  style={{ padding: '6px 14px' }}
                >
                  <span>Open Workspace</span>
                  <ChevronRight size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
