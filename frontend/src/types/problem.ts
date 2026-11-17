export type ProblemDifficulty = 
  | 'Div. 2 A (800-1100)'
  | 'Div. 2 B (1100-1400)'
  | 'Div. 2 C (1400-1600)'
  | 'Div. 2 D / Div. 1 B (1700-2000)'
  | 'Div. 1 C+ (2100+)';

export type ProblemStatus = 
  | 'draft'
  | 'generating'
  | 'generated'
  | 'verifying'
  | 'verified'
  | 'published'
  | 'failed';

export type SolutionTag = 'main' | 'accepted' | 'wrong-answer' | 'time-limit-exceeded';

export interface ProblemSolution {
  id: string;
  filename: string;
  tag: SolutionTag;
  description: string;
  code: string;
  language: string;
}

export interface ProblemSample {
  input: string;
  output: string;
  explanation?: string;
}

export interface ProblemArtifacts {
  statement: {
    legend: string;
    inputFormat: string;
    outputFormat: string;
    samples: ProblemSample[];
    notes: string;
  };
  editorial: {
    approach: string;
    complexityTime: string;
    complexitySpace: string;
    proof: string;
  };
  solutions: ProblemSolution[];
  validator: {
    filename: string;
    code: string;
    boundsNotes: string;
  };
  checker: {
    filename: string;
    type: 'standard' | 'custom';
    standardName?: string;
    code: string;
  };
  generators: {
    filename: string;
    code: string;
    scriptCommands: string[];
  }[];
  tests: {
    id: number;
    type: 'sample' | 'manual' | 'random' | 'adversarial';
    generatorCmd?: string;
    inputPreview: string;
    outputPreview?: string;
    validated: boolean;
  }[];
}

export interface VerificationReport {
  status: 'not_run' | 'passed' | 'failed' | 'warning';
  lastRunTimestamp?: string;
  compilation: {
    referenceSolution: boolean;
    bruteForceSolution: boolean;
    validator: boolean;
    checker: boolean;
    generators: boolean;
  };
  samplesPassed: number;
  totalSamples: number;
  stressTestsRun: number;
  stressTestsPassed: number;
  counterexamples: {
    testNumber: number;
    input: string;
    referenceOutput: string;
    bruteForceOutput: string;
  }[];
  waCandidatesCaught: number;
  totalWaCandidates: number;
  tleCandidatesTimedOut: number;
  totalTleCandidates: number;
  executionMetrics: {
    maxTimeMs: number;
    maxMemoryMb: number;
  };
}

export interface PolygonSyncStatus {
  linked: boolean;
  problemId?: string;
  problemUrl?: string;
  latestRevision?: number;
  packageBuildStatus: 'none' | 'pending' | 'ready' | 'warnings' | 'failed';
  lastSyncTime?: string;
  warnings?: string[];
  cautions?: string[];
}

export interface Problem {
  id: string;
  title: string;
  slug: string;
  shortIdea: string;
  difficulty: ProblemDifficulty;
  intendedAlgorithm: string;
  constraints: string;
  timeLimitMs: number;
  memoryLimitMb: number;
  preferredLanguage: string;
  status: ProblemStatus;
  createdAt: string;
  updatedAt: string;
  artifacts?: ProblemArtifacts;
  verification?: VerificationReport;
  polygon?: PolygonSyncStatus;
}
