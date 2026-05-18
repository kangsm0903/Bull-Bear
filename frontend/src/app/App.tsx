import { useState, useEffect, Component, type ReactNode, type ErrorInfo } from 'react';
import { InputScreen } from './components/InputScreen';
import { LoadingScreen } from './components/LoadingScreen';
import { DebateChat } from './components/DebateChat';
import type { DebateData } from './components/DebateChat';

// 전역 비동기 에러(setTimeout, Promise 등)를 잡아 화면에 표시
function useGlobalErrorCatcher(setGlobalError: (msg: string) => void) {
  useEffect(() => {
    const onError = (e: ErrorEvent) => {
      setGlobalError(`[window.onerror] ${e.message}\n  at ${e.filename}:${e.lineno}:${e.colno}\n${e.error?.stack ?? ''}`);
    };
    const onRejection = (e: PromiseRejectionEvent) => {
      setGlobalError(`[unhandledrejection] ${String(e.reason?.message ?? e.reason)}\n${e.reason?.stack ?? ''}`);
    };
    window.addEventListener('error', onError);
    window.addEventListener('unhandledrejection', onRejection);
    return () => {
      window.removeEventListener('error', onError);
      window.removeEventListener('unhandledrejection', onRejection);
    };
  }, [setGlobalError]);
}

class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  state = { error: null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info);
  }
  render() {
    if (this.state.error) {
      const err = this.state.error as Error;
      return (
        <div className="h-screen bg-black flex items-center justify-center p-8">
          <div className="max-w-xl w-full bg-rose-500/10 border border-rose-500/30 rounded-2xl p-6">
            <h2 className="text-rose-400 font-bold text-lg mb-2">🚨 렌더링 에러</h2>
            <p className="text-rose-300 font-mono text-sm mb-4 break-all">{err.message}</p>
            <pre className="text-slate-400 text-xs overflow-auto max-h-48">{err.stack}</pre>
            <button
              className="mt-4 px-4 py-2 bg-white/10 hover:bg-white/20 text-white rounded-lg text-sm"
              onClick={() => this.setState({ error: null })}
            >
              처음으로 돌아가기
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  const [debateTopic, setDebateTopic]   = useState<string | null>(null);
  const [isLoading, setIsLoading]       = useState(false);
  const [debateData, setDebateData]     = useState<DebateData | null>(null);
  const [error, setError]               = useState<string | null>(null);
  const [globalError, setGlobalError]   = useState<string | null>(null);

  useGlobalErrorCatcher(setGlobalError);

  const handleStartDebate = async (topic: string) => {
    setIsLoading(true);
    setDebateTopic(topic);
    setError(null);

    try {
      const res = await fetch('/api/debate', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ topic }),
      });

      if (!res.ok) throw new Error(`서버 오류: ${res.status}`);

      const data: DebateData = await res.json();
      setDebateData(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : '알 수 없는 오류');
      setDebateTopic(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleBack = () => {
    setDebateTopic(null);
    setDebateData(null);
    setError(null);
    setIsLoading(false);
  };

  return (
    <div className="size-full">
      {error && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 px-6 py-3 bg-rose-500/20 border border-rose-500/40 rounded-xl text-rose-400 text-sm">
          {error}
        </div>
      )}
      {globalError && (
        <div className="fixed bottom-4 left-4 right-4 z-50 p-4 bg-rose-900/95 border border-rose-500/40 rounded-xl text-rose-100 text-xs max-h-64 overflow-auto">
          <div className="flex justify-between mb-2">
            <strong className="text-rose-300">🚨 Global Error</strong>
            <button onClick={() => setGlobalError(null)} className="text-rose-300 hover:text-white">✕</button>
          </div>
          <pre className="whitespace-pre-wrap font-mono">{globalError}</pre>
        </div>
      )}
      <ErrorBoundary>
        {isLoading ? (
          <LoadingScreen topic={debateTopic!} />
        ) : debateTopic && debateData ? (
          <DebateChat topic={debateTopic} debateData={debateData} onBack={handleBack} />
        ) : (
          <InputScreen onStartDebate={handleStartDebate} />
        )}
      </ErrorBoundary>
    </div>
  );
}
