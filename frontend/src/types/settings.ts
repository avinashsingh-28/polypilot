export type AIProviderId = 'gemini' | 'openai' | 'anthropic' | 'groq' | 'ollama';

export interface AIProviderModel {
  id: string;
  name: string;
  contextWindow: string;
  recommended: boolean;
}

export interface AIProviderConfig {
  id: AIProviderId;
  name: string;
  description: string;
  models: AIProviderModel[];
  selectedModel: string;
  apiKey: string;
  isConfigured: boolean;
  status: 'disconnected' | 'testing' | 'connected' | 'error';
  lastTested?: string;
  customEndpoint?: string;
}

export interface PolygonConfig {
  apiKey: string;
  apiSecret: string;
  apiUrl: string;
  isConfigured: boolean;
  status: 'disconnected' | 'testing' | 'connected' | 'error';
  lastTested?: string;
  authorizedUser?: string;
}

export interface AppSettings {
  theme: 'light' | 'dark' | 'system';
  compilerStandard: 'c++17' | 'c++20';
  defaultTimeLimitMs: number;
  defaultMemoryLimitMb: number;
  autoSaveDrafts: boolean;
}
