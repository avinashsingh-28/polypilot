import React, { useState } from 'react';
import { 
  Sparkles, 
  ChevronDown, 
  ChevronUp, 
  AlertCircle, 
  CheckCircle2, 
  ArrowRight,
  Info,
  Clock,
  Cpu,
  Layers
} from 'lucide-react';
import { Problem, ProblemDifficulty } from '../types/problem';

interface NewProblemPageProps {
  onCreateDraft: (problem: Problem) => void | Promise<void>;
  onNavigateProblems: () => void;
}

export const NewProblemPage: React.FC<NewProblemPageProps> = ({
  onCreateDraft,
  onNavigateProblems
}) => {
  const [title, setTitle] = useState('');
  const [shortIdea, setShortIdea] = useState('');
  const [intendedAlgorithm, setIntendedAlgorithm] = useState('');
  const [constraints, setConstraints] = useState('');
  const [inputDescription, setInputDescription] = useState('');
  const [outputDescription, setOutputDescription] = useState('');
  const [timeLimitMs, setTimeLimitMs] = useState(2000);
  const [memoryLimitMb, setMemoryLimitMb] = useState(256);
  const [difficulty, setDifficulty] = useState<ProblemDifficulty>('Div. 2 C (1400-1600)');
  const [preferredLanguage, setPreferredLanguage] = useState('C++17');
  const [sampleInput, setSampleInput] = useState('');
  const [sampleOutput, setSampleOutput] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Advanced fields
  const [generatorCount, setGeneratorCount] = useState(3);
  const [customChecker, setCustomChecker] = useState(false);
  const [bruteForceThreshold, setBruteForceThreshold] = useState(15);
  const [stressTestCount, setStressTestCount] = useState(50);

  // Validation, submission & Phase Notice state
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submittedDraft, setSubmittedDraft] = useState<Problem | null>(null);

  const handleGenerateClick = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    // Validation: User must provide at least a short idea or title
    if (!shortIdea.trim() && !title.trim()) {
      setFormError('Please enter at least a Problem Title or a Short Problem Idea to proceed.');
      return;
    }

    const generatedSlug = (title || shortIdea.slice(0, 24))
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/(^-|-$)/g, '');

    const newProblem: Problem = {
      id: `poly-${Date.now().toString().slice(-4)}`,
      title: title.trim() || 'Untitled Problem Concept',
      slug: generatedSlug || 'untitled-problem',
      shortIdea: shortIdea.trim(),
      difficulty,
      intendedAlgorithm: intendedAlgorithm.trim() || 'Algorithm to be deduced by AI',
      constraints: constraints.trim() || '1 <= n <= 200,000',
      timeLimitMs,
      memoryLimitMb,
      preferredLanguage,
      status: 'draft',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      artifacts: {
        statement: {
          legend: shortIdea.trim() || 'Problem statement formulation pending.',
          inputFormat: inputDescription.trim() || 'First line contains integer t...',
          outputFormat: outputDescription.trim() || 'Output result for each testcase...',
          samples: sampleInput.trim() ? [{ input: sampleInput, output: sampleOutput }] : [],
          notes: ''
        },
        editorial: {
          approach: intendedAlgorithm.trim() || 'Approach analysis will be synthesized in Phase 3.',
          complexityTime: 'O(N log N) expected',
          complexitySpace: 'O(N) expected',
          proof: ''
        },
        solutions: [],
        validator: { filename: 'validator.cpp', code: '// Validator to be generated in Phase 3\n', boundsNotes: '' },
        checker: { filename: 'checker.cpp', type: customChecker ? 'custom' : 'standard', standardName: 'ncmp.cpp', code: '' },
        generators: [],
        tests: []
      }
    };

    setSubmitting(true);
    try {
      await onCreateDraft(newProblem);
      setSubmittedDraft(newProblem);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to save problem';
      setFormError(`Save failed: ${msg}`);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ maxWidth: '880px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)' }}>
          Create New Problem
        </h1>
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Define your core idea. You can start with just a quick natural-language concept, or provide detailed constraints and sample cases.
        </p>
      </div>

      {/* Phase 3 Notice Banner if submitted */}
      {submittedDraft && (
        <div
          className="card"
          style={{
            padding: '18px 20px',
            backgroundColor: 'var(--info-bg)',
            borderColor: 'var(--info-border)',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--info-text)', fontWeight: 600, fontSize: '14px' }}>
            <CheckCircle2 size={18} />
            <span>Problem Form Validated & Saved as Local Draft!</span>
          </div>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            Your problem specification <strong>"{submittedDraft.title}"</strong> has been structured and recorded in local memory.
            <br />
            <strong>AI Artifact Generation</strong> (LaTeX statement, reference solution, testlib validator, and generator suite) will be activated in <strong>Phase 3</strong>. In the meantime, you can explore the draft in the problem workspace or inspect the demonstration problem.
          </p>
          <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
            <button
              onClick={onNavigateProblems}
              className="btn btn-primary"
              style={{ padding: '6px 14px', fontSize: '12px' }}
            >
              <span>View in My Problems</span>
              <ArrowRight size={13} />
            </button>
            <button
              onClick={() => setSubmittedDraft(null)}
              className="btn btn-secondary"
              style={{ padding: '6px 14px', fontSize: '12px' }}
            >
              <span>Create Another</span>
            </button>
          </div>
        </div>
      )}

      {/* Form Error Banner */}
      {formError && (
        <div
          className="card"
          style={{
            padding: '12px 16px',
            backgroundColor: 'var(--danger-bg)',
            borderColor: 'var(--danger-border)',
            color: 'var(--danger-text)',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            fontSize: '13px'
          }}
        >
          <AlertCircle size={16} />
          <span>{formError}</span>
        </div>
      )}

      {/* Main Creation Form */}
      <form onSubmit={handleGenerateClick} className="card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {/* Core Idea Section */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div className="form-group">
            <label className="form-label">Problem Title</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g. Subsegment XOR Partition, Tree Diameter Queries"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
            <span className="form-hint">Optional. If empty, the title will be derived from your idea.</span>
          </div>

          <div className="form-group">
            <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span>Problem Idea / Concept</span>
              <span style={{ color: 'var(--brand-primary)', fontSize: '11px', textTransform: 'none' }}>(Primary Input)</span>
            </label>
            <textarea
              className="form-textarea"
              style={{ minHeight: '120px' }}
              placeholder="Describe your algorithm or game concept in plain English or mathematical notation...&#10;Example: Given an array of n integers and a threshold k, count the number of ways to partition the array such that every subsegment's XOR sum is strictly greater than k."
              value={shortIdea}
              onChange={(e) => setShortIdea(e.target.value)}
            />
            <span className="form-hint">
              You can start with just this description. The AI specification agent will formalize constraints and edge cases.
            </span>
          </div>
        </div>

        {/* Algorithm, Constraints & Limits */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
          <div className="form-group">
            <label className="form-label">Intended Algorithm (Optional)</label>
            <input
              type="text"
              className="form-input"
              placeholder="e.g. Trie + DP, Segment Tree, Binary Lifting"
              value={intendedAlgorithm}
              onChange={(e) => setIntendedAlgorithm(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Estimated Difficulty</label>
            <select
              className="form-select"
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value as ProblemDifficulty)}
            >
              <option value="Div. 2 A (800-1100)">Div. 2 A (800-1100)</option>
              <option value="Div. 2 B (1100-1400)">Div. 2 B (1100-1400)</option>
              <option value="Div. 2 C (1400-1600)">Div. 2 C (1400-1600)</option>
              <option value="Div. 2 D / Div. 1 B (1700-2000)">Div. 2 D / Div. 1 B (1700-2000)</option>
              <option value="Div. 1 C+ (2100+)">Div. 1 C+ (2100+)</option>
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Preferred Solution Language</label>
            <select
              className="form-select"
              value={preferredLanguage}
              onChange={(e) => setPreferredLanguage(e.target.value)}
            >
              <option value="C++17">C++17 (Standard Polygon Default)</option>
              <option value="C++20">C++20</option>
              <option value="Python 3">Python 3</option>
              <option value="Java 17">Java 17</option>
            </select>
          </div>
        </div>

        {/* Input/Output and Constraints */}
        <div className="form-group">
          <label className="form-label">Constraints (Optional)</label>
          <input
            type="text"
            className="form-input"
            placeholder="e.g. 1 <= n <= 200,000, 0 <= a_i, k < 2^30. Sum of n <= 200,000."
            value={constraints}
            onChange={(e) => setConstraints(e.target.value)}
          />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px' }}>
          <div className="form-group">
            <label className="form-label">Input Format (Optional)</label>
            <textarea
              className="form-textarea"
              placeholder="e.g. First line contains t (1 <= t <= 10^4). Each testcase has n and k followed by array elements."
              value={inputDescription}
              onChange={(e) => setInputDescription(e.target.value)}
              style={{ minHeight: '70px' }}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Output Format (Optional)</label>
            <textarea
              className="form-textarea"
              placeholder="e.g. Output the answer modulo 998244353 for each test case on a new line."
              value={outputDescription}
              onChange={(e) => setOutputDescription(e.target.value)}
              style={{ minHeight: '70px' }}
            />
          </div>
        </div>

        {/* Execution Limits */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          <div className="form-group">
            <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <Clock size={12} />
              <span>Time Limit (ms)</span>
            </label>
            <input
              type="number"
              className="form-input"
              value={timeLimitMs}
              onChange={(e) => setTimeLimitMs(Number(e.target.value))}
              min={250}
              max={10000}
              step={250}
            />
          </div>

          <div className="form-group">
            <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <Cpu size={12} />
              <span>Memory Limit (MB)</span>
            </label>
            <input
              type="number"
              className="form-input"
              value={memoryLimitMb}
              onChange={(e) => setMemoryLimitMb(Number(e.target.value))}
              min={64}
              max={1024}
              step={64}
            />
          </div>
        </div>

        {/* Optional Samples */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px' }}>
          <div className="form-group">
            <label className="form-label">Sample Input (Optional)</label>
            <textarea
              className="form-textarea"
              placeholder="2&#10;4 2&#10;3 1 4 2&#10;3 0&#10;1 2 3"
              value={sampleInput}
              onChange={(e) => setSampleInput(e.target.value)}
              style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', minHeight: '80px' }}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Sample Output (Optional)</label>
            <textarea
              className="form-textarea"
              placeholder="2&#10;3"
              value={sampleOutput}
              onChange={(e) => setSampleOutput(e.target.value)}
              style={{ fontFamily: 'var(--font-mono)', fontSize: '12px', minHeight: '80px' }}
            />
          </div>
        </div>

        {/* Expandable Advanced Configuration */}
        <div
          style={{
            borderTop: '1px solid var(--border-subtle)',
            paddingTop: '16px'
          }}
        >
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="btn btn-ghost"
            style={{ padding: '6px 0', fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)' }}
          >
            {showAdvanced ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            <span>Advanced Configuration (Testlib, Stress Testing, Custom Checker)</span>
          </button>

          {showAdvanced && (
            <div
              style={{
                marginTop: '12px',
                padding: '16px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: 'var(--bg-surface-subtle)',
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                gap: '16px'
              }}
            >
              <div className="form-group">
                <label className="form-label">Generators Count</label>
                <input
                  type="number"
                  className="form-input"
                  value={generatorCount}
                  onChange={(e) => setGeneratorCount(Number(e.target.value))}
                  min={1}
                  max={10}
                />
                <span className="form-hint">Number of distinct testlib generators</span>
              </div>

              <div className="form-group">
                <label className="form-label">Differential Stress Tests</label>
                <input
                  type="number"
                  className="form-input"
                  value={stressTestCount}
                  onChange={(e) => setStressTestCount(Number(e.target.value))}
                  min={10}
                  max={500}
                />
                <span className="form-hint">Reference vs. Brute-force comparison cycles</span>
              </div>

              <div className="form-group">
                <label className="form-label">Brute Force Max N Threshold</label>
                <input
                  type="number"
                  className="form-input"
                  value={bruteForceThreshold}
                  onChange={(e) => setBruteForceThreshold(Number(e.target.value))}
                  min={5}
                  max={2000}
                />
                <span className="form-hint">Max input size for slow solutions during testing</span>
              </div>

              <div className="form-group" style={{ justifyContent: 'center' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '13px', color: 'var(--text-primary)', marginTop: '18px' }}>
                  <input
                    type="checkbox"
                    checked={customChecker}
                    onChange={(e) => setCustomChecker(e.target.checked)}
                    style={{ accentColor: 'var(--brand-primary)' }}
                  />
                  <span>Require Custom Testlib Checker</span>
                </label>
                <span className="form-hint">Default uses standard tokens/floats/integers comparator</span>
              </div>
            </div>
          )}
        </div>

        {/* Action Button */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid var(--border-subtle)', paddingTop: '16px' }}>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Validation will verify form inputs before saving.
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            disabled={submitting}
            style={{ padding: '9px 20px', fontSize: '14px', fontWeight: 600, opacity: submitting ? 0.7 : 1 }}
          >
            <Sparkles size={16} />
            <span>{submitting ? 'Saving…' : 'Generate Problem'}</span>
          </button>
        </div>
      </form>
    </div>
  );
};
