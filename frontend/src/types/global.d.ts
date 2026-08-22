/**
 * Global Window and Event Declarations for Butler Desktop Frontend
 */

import type { PyWebView } from './pywebview';

export interface BridgeResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

export interface BHLMessage<T = any> {
  type: 'command' | 'response' | 'event' | 'voice_stream' | 'status_update';
  action: string;
  payload: T;
  timestamp: number;
  requestId?: string;
}

export interface BHLCommandPayload {
  cmd: string;
  args?: Record<string, any>;
  source?: 'voice' | 'flash_input' | 'gui' | 'terminal';
}

export interface VoiceRecognizedEvent {
  text: string;
  confidence: number;
  isFinal: boolean;
  commandMatched?: string;
}

export interface VoiceStatus {
  isListening: boolean;
  isSpeaking: boolean;
  wakeWordDetected: boolean;
  engine: 'web_speech' | 'wasm_whisper' | 'python_backend';
  volume: number;
}

export interface MemoItem {
  id: number;
  content: string;
  tags?: string[];
  resources?: string[];
  created_at: number;
  is_pinned?: number;
  is_archived?: number;
}

export interface WorkflowItem {
  name: string;
  status: 'running' | 'completed' | 'failed' | string;
  current_step: number;
  steps: Array<{ intent: string; [key: string]: any }>;
}

declare global {
  interface Window {
    pywebview?: PyWebView;
    modernBridge?: any;

    // Voice & Visualizer Singletons
    voiceEngine?: any;
    wakeWordDetector?: any;
    ringVisualizer?: any;
    bhlClient?: any;
    glassUI?: any;

    // Singletons / Modules
    stateMatrix?: any;
    StateMatrix?: any;
    matrix?: any;
    telemetryManager?: any;
    dagEngine?: any;
    timeMachine?: any;
    TimeMachine?: any;
    subtleHeatmap?: any;
    wormhole?: any;
    timeSlitEditor?: any;
    vault?: any;
    modalManager?: any;
    memosManager?: any;
    browserModal?: any;
    floatingPopupManager?: any;
    FloatingPopupManager?: any;
    FloatingPopup?: any;
    featuresHub?: any;
    FeaturesHub?: any;
    skillUiLoader?: any;
    SpringPhysics?: any;

    // UI Utility Functions
    showToast?: (title: string, message: string, type?: 'success' | 'error' | 'warning' | 'info') => void;
    escapeHTML?: (str: string) => string;
    triggerQuickAction?: (command: string, emoji?: string) => void;
    toggleInterfaceMode?: () => void;
    toggleSettings?: () => void;
    switchSettingsTab?: (tabId: string) => void;
    toggleApiKeyVisibility?: () => void;
    onProviderChange?: () => void;
    saveModelSettings?: () => void;
    onMemoryDbChange?: () => void;
    saveMemorySettings?: () => void;
    testHalConnection?: () => void;
    toggleThemeMode?: () => void;
    updateBlurValue?: (val: string | number) => void;
    updateFontFamily?: (val: string) => void;
    updateFontSize?: (val: string) => void;
    launchPixelPet?: () => Promise<void>;
    toggleHeatmapAnimation?: () => void;
    onVaultUnlocking?: (data: any) => void;
    toggleTerminal?: () => void;
    toggleMemos?: () => void;
    runDagPipeline?: () => void;
    pauseDagPipeline?: () => void;
    clearDagCanvas?: () => void;
    startOnboardingTour?: () => void;
    nextOnboardingStep?: () => void;
    skipOnboarding?: () => void;

    // Voice Callbacks
    onVoiceStatusChange?: (isListening: boolean) => void;
    onWakeWordDetected?: (wakeWord: string) => void;
    onVoiceCommandRecognized?: (cmd: string) => void;

    // Event Stream callbacks
    onAIStreamStart?: () => void;
    onAIStreamChunk?: (chunk: string) => void;
    onAIStreamEnd?: () => void;

    // Terminal
    term?: any;
    NativePort?: MessagePort;

    // Libraries from CDN
    monaco_ready?: boolean;
    monaco?: any;
    require?: any;
    pdfjsLib?: any;
    Terminal?: any;
    FitAddon?: any;
    marked?: any;
    DOMPurify?: any;
    vis?: any;
  }
}

export {};
