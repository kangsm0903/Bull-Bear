import { useState } from 'react';
import { TrendingUp, TrendingDown, Search } from 'lucide-react';

export interface Survey {
  level?: string;
  terminology?: string;
  depth?: string;
  horizon?: string;
}

interface InputScreenProps {
  onStartDebate: (topic: string, survey: Survey) => void;
}

const SURVEY_QUESTIONS: { field: keyof Survey; label: string; options: string[] }[] = [
  { field: 'level',       label: '개인 수준', options: ['입문자', '개인투자자', '전문가'] },
  { field: 'terminology', label: '용어 숙지', options: ['낮음', '보통', '높음'] },
  { field: 'depth',       label: '설명 깊이', options: ['쉽고 간단', '균형', '심층·정밀'] },
  { field: 'horizon',     label: '희망 투자 기간', options: ['단기', '중기', '장기'] },
];

export function InputScreen({ onStartDebate }: InputScreenProps) {
  const [topic, setTopic] = useState('');
  const [focusedExample, setFocusedExample] = useState<number | null>(null);
  const [survey, setSurvey] = useState<Survey>({});

  const toggleField = (field: keyof Survey, value: string) => {
    setSurvey((prev) => ({ ...prev, [field]: prev[field] === value ? undefined : value }));
  };

  const exampleTopics = [
    { ticker: '005930', name: '삼성전자',   topic: 'HBM·파운드리 수익성 회복 가능성',  sentiment: 'bullish' },
    { ticker: '000660', name: 'SK하이닉스', topic: 'AI 반도체 수요 지속 여부',           sentiment: 'bullish' },
    { ticker: '005380', name: '현대차',     topic: '전기차 전환 속도와 수익성 균형',     sentiment: 'neutral' },
    { ticker: '066570', name: 'LG전자',     topic: 'VS사업부 성장세와 가전 사이클 전망', sentiment: 'neutral' },
  ];

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (topic.trim()) {
      onStartDebate(topic.trim(), survey);
    }
  };

  return (
    <div className="min-h-screen relative overflow-hidden bg-black">
      {/* Animated background */}
      <div className="absolute inset-0">
        <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 via-black to-rose-500/5" />
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl animate-pulse" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-rose-500/10 rounded-full blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
      </div>

      <div className="relative min-h-screen flex items-center justify-center p-6">
        <div className="w-full max-w-4xl">
          {/* Header */}
          <div className="text-center mb-16">
            <div className="relative mb-6">
              <div className="flex items-center justify-center gap-6">
                <div className="group flex items-center gap-3">
                  <div className="relative">
                    <div className="absolute inset-0 bg-emerald-500 blur-xl opacity-50 group-hover:opacity-75 transition-opacity" />
                    <div className="relative w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center transform group-hover:scale-110 transition-transform">
                      <TrendingUp className="w-8 h-8 text-white" strokeWidth={2.5} />
                    </div>
                  </div>
                  <span className="text-5xl font-bold bg-gradient-to-r from-emerald-400 to-emerald-500 bg-clip-text text-transparent">
                    Bull
                  </span>
                </div>

                <div className="w-px h-16 bg-gradient-to-b from-transparent via-white/20 to-transparent" />

                <div className="group flex items-center gap-3">
                  <span className="text-5xl font-bold bg-gradient-to-r from-rose-500 to-rose-400 bg-clip-text text-transparent">
                    Bear
                  </span>
                  <div className="relative">
                    <div className="absolute inset-0 bg-rose-500 blur-xl opacity-50 group-hover:opacity-75 transition-opacity" />
                    <div className="relative w-16 h-16 rounded-2xl bg-gradient-to-br from-rose-600 to-rose-400 flex items-center justify-center transform group-hover:scale-110 transition-transform">
                      <TrendingDown className="w-8 h-8 text-white" strokeWidth={2.5} />
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <h1 className="text-2xl text-slate-400 font-light mb-3">
              Dual-Perspective Investment Analysis
            </h1>
            <p className="text-slate-500 max-w-2xl mx-auto leading-relaxed">
              Advanced AI agents analyze both sides of your investment thesis, providing comprehensive insights through structured debate and real-time market data
            </p>
          </div>

          {/* Search Form */}
          <form onSubmit={handleSubmit} className="space-y-8">
            <div className="relative group">
              <div className="absolute -inset-0.5 bg-gradient-to-r from-emerald-500 to-rose-500 rounded-2xl opacity-20 group-focus-within:opacity-40 blur transition-opacity" />
              <div className="relative flex items-center bg-white/5 border border-white/10 rounded-2xl overflow-hidden backdrop-blur-xl">
                <div className="pl-6">
                  <Search className="w-6 h-6 text-slate-500" />
                </div>
                <input
                  type="text"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="종목명 또는 티커 입력 (예: 삼성전자, 005930)"
                  className="flex-1 px-6 py-5 bg-transparent text-white placeholder-slate-500 focus:outline-none text-lg"
                />
                {topic && (
                  <button
                    type="submit"
                    className="mx-3 px-6 py-3 bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white font-medium rounded-xl transition-all shadow-lg shadow-emerald-500/20"
                  >
                    Analyze
                  </button>
                )}
              </div>
            </div>

            {/* Reader Profile Survey (optional) */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-slate-400 uppercase tracking-wider">
                  독자 프로필 <span className="text-slate-600 normal-case">(선택 — 답변 수준이 맞춰집니다)</span>
                </p>
                <div className="h-px flex-1 ml-4 bg-gradient-to-r from-white/10 to-transparent" />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4 p-5 bg-white/5 border border-white/10 rounded-xl">
                {SURVEY_QUESTIONS.map((q) => (
                  <div key={q.field} className="space-y-2">
                    <p className="text-xs text-slate-500">{q.label}</p>
                    <div className="flex flex-wrap gap-2">
                      {q.options.map((opt) => {
                        const selected = survey[q.field] === opt;
                        return (
                          <button
                            key={opt}
                            type="button"
                            onClick={() => toggleField(q.field, opt)}
                            className={`px-3 py-1.5 rounded-lg text-sm transition-all border ${
                              selected
                                ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-300'
                                : 'bg-white/5 border-white/10 text-slate-400 hover:bg-white/10 hover:text-slate-300'
                            }`}
                          >
                            {opt}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Example Topics */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-slate-400 uppercase tracking-wider">
                  입력 예시
                </p>
                <div className="h-px flex-1 ml-4 bg-gradient-to-r from-white/10 to-transparent" />
              </div>

              <div className="grid grid-cols-2 gap-3">
                {exampleTopics.map((example, index) => (
                  <button
                    key={index}
                    type="button"
                    onClick={() => setTopic(example.name)}
                    onMouseEnter={() => setFocusedExample(index)}
                    onMouseLeave={() => setFocusedExample(null)}
                    className="relative group text-left p-5 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 hover:border-white/20 transition-all overflow-hidden"
                  >
                    <div className={`absolute inset-0 bg-gradient-to-br opacity-0 group-hover:opacity-10 transition-opacity ${
                      example.sentiment === 'bullish' ? 'from-emerald-500 to-transparent' : 'from-slate-500 to-transparent'
                    }`} />

                    <div className="relative flex items-start justify-between mb-3">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-lg font-bold text-white">{example.ticker}</span>
                          <span className={`w-1.5 h-1.5 rounded-full ${
                            example.sentiment === 'bullish' ? 'bg-emerald-500' : 'bg-slate-500'
                          }`} />
                        </div>
                        <p className="text-sm text-slate-400">{example.name}</p>
                      </div>
                      <div className={`transform transition-transform ${focusedExample === index ? 'translate-x-0' : 'translate-x-1'} opacity-50 group-hover:opacity-100`}>
                        <Search className="w-4 h-4 text-slate-400" />
                      </div>
                    </div>

                    <p className="relative text-sm text-slate-500 leading-relaxed">
                      {example.topic}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          </form>

          {/* Footer Info */}
          <div className="mt-12 flex items-center justify-center gap-8 text-sm text-slate-600">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-emerald-500" />
              <span>Real-time Analysis</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-blue-500" />
              <span>Multi-source Data</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-amber-500" />
              <span>AI-Powered Insights</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
