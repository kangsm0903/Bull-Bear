import { useState, useEffect, useRef } from 'react';
import { DebateMessage } from './DebateMessage';
import { ArticleReference, Article } from './ArticleReference';
import { ArrowLeft, Activity, TrendingUp, TrendingDown, BarChart3 } from 'lucide-react';
import { motion } from 'motion/react';

interface Message {
  id:        string;
  agent:     'bull' | 'bear';
  kind?:     'argue' | 'rebut' | 'conclude';
  round?:    number;
  message:   string;
  timestamp: string;
}

interface Moderator {
  bull_summary: string;
  bear_summary: string;
  conclusion:   string;
  verdict:      string;
  data_balance: string;
}

export interface DebateData {
  messages:   Message[];
  articles:   Article[];
  bull_score: number;
  bear_score: number;
  moderator:  Moderator;
}

interface DebateChatProps {
  topic:       string;
  debateData:  DebateData;
  onBack:      () => void;
}

const VERDICT_LABEL: Record<string, string> = {
  '매수 적극': '🚀 Strong Buy',
  '분할 매수': '📈 Accumulate',
  '관망':      '👀 Hold / Watch',
  '매도 고려': '📉 Consider Sell',
};

export function DebateChat({ topic, debateData, onBack }: DebateChatProps) {
  const [visibleMessages, setVisibleMessages] = useState<Message[]>([]);
  const [showModerator, setShowModerator]     = useState(false);
  const [isPlaying, setIsPlaying]             = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { messages, articles, bull_score, bear_score, moderator } = debateData;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [visibleMessages, showModerator]);

  // 메시지를 1.5초 간격으로 순차 출력
  useEffect(() => {
    setVisibleMessages([]);
    setShowModerator(false);
    setIsPlaying(true);

    if (!messages || messages.length === 0) {
      setShowModerator(true);
      setIsPlaying(false);
      return;
    }

    let count = 0;
    const interval = setInterval(() => {
      count += 1;
      // slice로 prefix만 보여주므로 undefined가 들어갈 수 없음
      setVisibleMessages(messages.slice(0, count));
      if (count >= messages.length) {
        clearInterval(interval);
        const moderatorTimer = setTimeout(() => setShowModerator(true), 1000);
        setIsPlaying(false);
        // cleanup용 핸들은 outer scope에 없으므로 컴포넌트 unmount 시 React가 무시
        void moderatorTimer;
      }
    }, 1500);

    return () => clearInterval(interval);
  }, [messages]);

  return (
    <div className="h-screen flex bg-black relative overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0">
        <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 via-black to-rose-500/5" />
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-emerald-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-rose-500/5 rounded-full blur-3xl" />
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col relative">
        {/* Header */}
        <div className="bg-black/40 backdrop-blur-xl border-b border-white/10 px-8 py-5">
          <div className="flex items-center justify-between mb-4">
            <button
              onClick={onBack}
              className="flex items-center gap-2 text-slate-500 hover:text-white transition-colors group"
            >
              <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center group-hover:bg-white/10 transition-colors">
                <ArrowLeft className="w-4 h-4" />
              </div>
              <span className="text-sm font-medium">Back to Search</span>
            </button>

            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
              <Activity className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-xs font-medium text-emerald-400">Live Analysis</span>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-white mb-1">{topic}</h1>
              <p className="text-sm text-slate-400">AI agents are conducting real-time debate analysis</p>
            </div>

            <div className="flex items-center gap-4">
              {/* Bull Score */}
              <div className="flex items-center gap-2">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-600 flex items-center justify-center">
                  <TrendingUp className="w-5 h-5 text-white" strokeWidth={2.5} />
                </div>
                <div>
                  <div className="text-xs text-slate-500">Bull Score</div>
                  <div className="text-sm font-bold text-emerald-400">{bull_score}/10</div>
                </div>
              </div>

              <div className="w-px h-10 bg-white/10" />

              {/* Bear Score */}
              <div className="flex items-center gap-2">
                <div>
                  <div className="text-xs text-slate-500 text-right">Bear Score</div>
                  <div className="text-sm font-bold text-rose-400 text-right">{bear_score}/10</div>
                </div>
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-rose-500 to-rose-600 flex items-center justify-center">
                  <TrendingDown className="w-5 h-5 text-white" strokeWidth={2.5} />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-8 space-y-6">
          {visibleMessages.filter(Boolean).map((msg, idx, arr) => {
            const prev = arr[idx - 1];
            const showRoundDivider = msg.round && (!prev || prev.round !== msg.round);
            const roundMeta: Record<number, { name: string; sub: string; color: string }> = {
              1: { name: 'ROUND 1', sub: '정성 분석 · 뉴스 기사',          color: 'from-blue-500/30 to-blue-500/0' },
              2: { name: 'ROUND 2', sub: '정량 분석 · 재무/컨센서스/주가', color: 'from-purple-500/30 to-purple-500/0' },
              3: { name: 'ROUND 3', sub: '최종 결론 · 통합 분석',          color: 'from-amber-500/30 to-amber-500/0' },
            };
            const meta = msg.round ? roundMeta[msg.round] : undefined;
            return (
              <div key={msg.id}>
                {showRoundDivider && meta && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.4 }}
                    className="my-10"
                  >
                    <div className="flex items-center gap-4">
                      <div className={`h-px flex-1 bg-gradient-to-r ${meta.color}`} />
                      <div className="flex flex-col items-center text-center px-6 py-3 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-sm min-w-[240px]">
                        <span className="text-xs font-mono text-slate-500 tracking-widest mb-1">{meta.name}</span>
                        <span className="text-base font-bold text-white">{meta.sub}</span>
                      </div>
                      <div className={`h-px flex-1 bg-gradient-to-l ${meta.color}`} />
                    </div>
                  </motion.div>
                )}
                <DebateMessage
                  agent={msg.agent}
                  message={msg.message}
                  timestamp={msg.timestamp}
                  kind={msg.kind}
                />
              </div>
            );
          })}

          {/* 로딩 인디케이터 */}
          {isPlaying && (
            <div className="flex items-center justify-center gap-3 py-4">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" />
                <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" style={{ animationDelay: '200ms' }} />
                <div className="w-2 h-2 bg-rose-500 rounded-full animate-pulse" style={{ animationDelay: '400ms' }} />
              </div>
              <span className="text-sm text-slate-500 font-medium">Analyzing market data...</span>
            </div>
          )}

          {/* Moderator 결론 */}
          {showModerator && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="p-6 rounded-2xl bg-gradient-to-br from-blue-500/10 to-blue-600/5 border border-blue-500/20"
            >
              <div className="flex items-center gap-2 mb-4">
                <div className="w-8 h-8 rounded-lg bg-blue-500/20 border border-blue-500/30 flex items-center justify-center text-sm">⚖️</div>
                <span className="text-xs font-semibold text-blue-400 uppercase tracking-wider">Moderator · Final Verdict</span>
              </div>
              <p className="text-sm text-slate-300 leading-relaxed mb-2">
                <span className="text-emerald-400 font-semibold">Bull: </span>{moderator.bull_summary}
              </p>
              <p className="text-sm text-slate-300 leading-relaxed mb-3">
                <span className="text-rose-400 font-semibold">Bear: </span>{moderator.bear_summary}
              </p>
              <p className="text-sm text-slate-200 leading-relaxed mb-4">{moderator.conclusion}</p>
              <div className="inline-flex items-center px-4 py-1.5 rounded-full bg-blue-500/10 border border-blue-500/30 text-blue-300 text-sm font-semibold">
                {VERDICT_LABEL[moderator.verdict] ?? moderator.verdict}
              </div>
              {moderator.data_balance && (
                <p className="mt-3 text-xs text-slate-400 leading-relaxed">
                  <span className="text-slate-500">근거 균형 · </span>{moderator.data_balance}
                </p>
              )}
            </motion.div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Articles Sidebar */}
      <div className="w-96 bg-black/40 backdrop-blur-xl border-l border-white/10 flex flex-col relative">
        <div className="px-6 py-5 border-b border-white/10">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
              <BarChart3 className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <h2 className="font-semibold text-white">Source Materials</h2>
              <p className="text-xs text-slate-500">{articles.length} articles referenced</p>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {articles.map((article, index) => (
            <motion.div
              key={article.id}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <ArticleReference article={article} />
            </motion.div>
          ))}
        </div>

        {/* Stats Footer */}
        <div className="p-4 border-t border-white/10">
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
              <div className="text-xs text-slate-500 mb-1">Bull Sources</div>
              <div className="text-lg font-bold text-emerald-400">
                {articles.filter(a => a.referencedBy === 'bull').length}
              </div>
            </div>
            <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
              <div className="text-xs text-slate-500 mb-1">Shared</div>
              <div className="text-lg font-bold text-blue-400">
                {articles.filter(a => a.referencedBy === 'both').length}
              </div>
            </div>
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20">
              <div className="text-xs text-slate-500 mb-1">Bear Sources</div>
              <div className="text-lg font-bold text-rose-400">
                {articles.filter(a => a.referencedBy === 'bear').length}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
