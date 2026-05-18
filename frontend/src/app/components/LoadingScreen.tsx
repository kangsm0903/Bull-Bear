import { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Activity, BarChart3, FileText, Sparkles } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

interface LoadingScreenProps {
  topic: string;
}

const CYCLING_STAGES = [
  { icon: FileText,   label: '관련 뉴스 기사 검색 중...',         color: 'blue'    },
  { icon: BarChart3,  label: '정량 데이터 수집 중...',            color: 'purple'  },
  { icon: TrendingUp, label: 'Bull 애널리스트 Round 1 분석 중...', color: 'emerald' },
  { icon: TrendingDown, label: 'Bear 애널리스트 Round 1 반박 중...', color: 'rose'  },
  { icon: BarChart3,  label: 'Round 2 정량 데이터 기반 토론 중...', color: 'purple' },
  { icon: Activity,   label: 'Round 3 통합 분석 진행 중...',       color: 'amber'   },
  { icon: Sparkles,   label: 'Moderator 최종 결론 도출 중...',     color: 'blue'    },
];

export function LoadingScreen({ topic }: LoadingScreenProps) {
  const [stageIndex, setStageIndex] = useState(0);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const stageTimer = setInterval(() => {
      setStageIndex(prev => (prev + 1) % CYCLING_STAGES.length);
    }, 8000);
    return () => clearInterval(stageTimer);
  }, []);

  useEffect(() => {
    const clock = setInterval(() => setElapsed(s => s + 1), 1000);
    return () => clearInterval(clock);
  }, []);

  const stages = CYCLING_STAGES;

  return (
    <div className="h-screen relative overflow-hidden bg-black flex items-center justify-center">
      {/* Animated background */}
      <div className="absolute inset-0">
        <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 via-black to-rose-500/5" />
        <motion.div
          className="absolute top-1/4 left-1/4 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl"
          animate={{
            scale: [1, 1.2, 1],
            opacity: [0.3, 0.5, 0.3],
          }}
          transition={{
            duration: 3,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />
        <motion.div
          className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-rose-500/10 rounded-full blur-3xl"
          animate={{
            scale: [1, 1.2, 1],
            opacity: [0.3, 0.5, 0.3],
          }}
          transition={{
            duration: 3,
            repeat: Infinity,
            ease: 'easeInOut',
            delay: 1.5,
          }}
        />
      </div>

      <div className="relative z-10 max-w-2xl mx-auto px-6">
        {/* Main loading animation */}
        <div className="text-center mb-12">
          <motion.div
            className="flex items-center justify-center gap-8 mb-8"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
          >
            {/* Bull Icon */}
            <motion.div
              className="relative"
              animate={{
                y: [0, -10, 0],
              }}
              transition={{
                duration: 2,
                repeat: Infinity,
                ease: 'easeInOut',
              }}
            >
              <div className="absolute inset-0 bg-emerald-500 blur-xl opacity-50" />
              <div className="relative w-20 h-20 rounded-2xl bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center shadow-2xl">
                <TrendingUp className="w-10 h-10 text-white" strokeWidth={2.5} />
              </div>
            </motion.div>

            {/* VS Divider */}
            <div className="relative">
              <motion.div
                className="absolute inset-0 bg-blue-500 blur-xl opacity-30"
                animate={{
                  opacity: [0.3, 0.6, 0.3],
                }}
                transition={{
                  duration: 2,
                  repeat: Infinity,
                }}
              />
              <div className="relative text-3xl font-bold text-white/50">VS</div>
            </div>

            {/* Bear Icon */}
            <motion.div
              className="relative"
              animate={{
                y: [0, -10, 0],
              }}
              transition={{
                duration: 2,
                repeat: Infinity,
                ease: 'easeInOut',
                delay: 1,
              }}
            >
              <div className="absolute inset-0 bg-rose-500 blur-xl opacity-50" />
              <div className="relative w-20 h-20 rounded-2xl bg-gradient-to-br from-rose-600 to-rose-400 flex items-center justify-center shadow-2xl">
                <TrendingDown className="w-10 h-10 text-white" strokeWidth={2.5} />
              </div>
            </motion.div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.3 }}
          >
            <h2 className="text-2xl font-bold text-white mb-2">Analyzing {topic}</h2>
            <p className="text-slate-400">
              AI agents are preparing comprehensive debate analysis
            </p>
          </motion.div>
        </div>

        {/* Active stage card */}
        <motion.div
          className="space-y-4"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
        >
          {/* Completed stages (dimmed) */}
          {stages.slice(0, stageIndex).map((stage, index) => {
            const Icon = stage.icon;
            return (
              <div key={index} className="flex items-center gap-4 p-3 rounded-xl opacity-30">
                <div className="w-8 h-8 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center flex-shrink-0">
                  <Icon className="w-4 h-4 text-slate-500" />
                </div>
                <p className="text-slate-500 text-sm line-through">{stage.label}</p>
                <div className="ml-auto text-slate-600 text-xs">✓</div>
              </div>
            );
          })}

          {/* Current active stage */}
          <AnimatePresence mode="wait">
            {(() => {
              const stage = stages[stageIndex];
              const Icon = stage.icon;
              const colorClasses = {
                blue:    'bg-blue-500/10 border-blue-500/20 text-blue-400',
                purple:  'bg-purple-500/10 border-purple-500/20 text-purple-400',
                amber:   'bg-amber-500/10 border-amber-500/20 text-amber-400',
                emerald: 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400',
                rose:    'bg-rose-500/10 border-rose-500/20 text-rose-400',
              }[stage.color] ?? 'bg-blue-500/10 border-blue-500/20 text-blue-400';
              const dotColor = {
                blue: 'bg-blue-400', purple: 'bg-purple-400',
                amber: 'bg-amber-400', emerald: 'bg-emerald-400', rose: 'bg-rose-400',
              }[stage.color] ?? 'bg-blue-400';

              return (
                <motion.div
                  key={stageIndex}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 20 }}
                  transition={{ duration: 0.4 }}
                >
                  <div className="flex items-center gap-4 p-4 bg-white/5 border border-white/10 rounded-xl backdrop-blur-sm">
                    <div className={`w-10 h-10 rounded-lg ${colorClasses} border flex items-center justify-center flex-shrink-0`}>
                      <Icon className="w-5 h-5" />
                    </div>
                    <div className="flex-1">
                      <p className="text-white font-medium">{stage.label}</p>
                    </div>
                    <div className="flex gap-1">
                      {[0, 1, 2].map((dotIndex) => (
                        <motion.div
                          key={dotIndex}
                          className={`w-1.5 h-1.5 rounded-full ${dotColor}`}
                          animate={{ opacity: [0.3, 1, 0.3], scale: [0.8, 1.2, 0.8] }}
                          transition={{ duration: 1.5, repeat: Infinity, delay: dotIndex * 0.2 }}
                        />
                      ))}
                    </div>
                  </div>
                </motion.div>
              );
            })()}
          </AnimatePresence>
        </motion.div>

        {/* Indeterminate loading bar */}
        <motion.div
          className="mt-8"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.5 }}
        >
          <div className="relative h-2 bg-white/5 rounded-full overflow-hidden">
            <motion.div
              className="absolute inset-y-0 bg-gradient-to-r from-emerald-500 via-blue-500 to-rose-500"
              style={{ width: '40%' }}
              animate={{ x: ['-40%', '260%'] }}
              transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
            />
          </div>
        </motion.div>

        {/* Elapsed time + estimate */}
        <motion.div
          className="flex items-center justify-between mt-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 2 }}
        >
          <p className="text-sm text-slate-500">
            경과 시간: <span className="text-slate-400 font-mono">
              {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, '0')}
            </span>
          </p>
          <p className="text-sm text-slate-500">보통 1~2분 소요됩니다</p>
        </motion.div>
      </div>
    </div>
  );
}
