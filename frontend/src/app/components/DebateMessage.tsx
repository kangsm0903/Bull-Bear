import { TrendingUp, TrendingDown } from 'lucide-react';
import { motion } from 'motion/react';

export type AgentType = 'bull' | 'bear';
export type MessageKind = 'argue' | 'rebut' | 'conclude';

interface DebateMessageProps {
  agent: AgentType;
  message: string;
  timestamp: string;
  kind?: MessageKind;
}

const KIND_LABEL: Record<AgentType, Record<MessageKind, string>> = {
  bull: {
    argue:    '찬성 주장',
    rebut:    '찬성 반론',
    conclude: '찬성 최종 결론',
  },
  bear: {
    argue:    '반대 주장',
    rebut:    '반대 반론',
    conclude: '반대 최종 결론',
  },
};

export function DebateMessage({ agent, message, timestamp, kind }: DebateMessageProps) {
  const isBull = agent === 'bull';
  const kindLabel = kind ? KIND_LABEL[agent][kind] : (isBull ? 'Bull Analysis' : 'Bear Analysis');

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: 'easeOut' }}
      className={`flex gap-4 ${isBull ? 'justify-start' : 'justify-end'}`}
    >
      {isBull && (
        <div className="flex-shrink-0 relative">
          <div className="absolute inset-0 bg-emerald-500 blur-lg opacity-30" />
          <div className="relative w-12 h-12 rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-600 flex items-center justify-center shadow-lg">
            <TrendingUp className="w-6 h-6 text-white" strokeWidth={2.5} />
          </div>
        </div>
      )}

      <div className={`flex flex-col max-w-[65%] ${isBull ? 'items-start' : 'items-end'}`}>
        <div className="flex items-center gap-2 mb-2 px-1">
          <span className={`text-xs font-semibold uppercase tracking-wider ${
            isBull ? 'text-emerald-400' : 'text-rose-400'
          }`}>
            {kindLabel}
          </span>
          <div className="h-1 w-1 rounded-full bg-slate-600" />
          <span className="text-xs text-slate-500 font-mono">{timestamp}</span>
        </div>

        <div className="relative group">
          <div className={`absolute -inset-0.5 bg-gradient-to-br opacity-0 group-hover:opacity-100 rounded-2xl blur transition-opacity ${
            isBull
              ? 'from-emerald-500/20 to-emerald-600/20'
              : 'from-rose-500/20 to-rose-600/20'
          }`} />
          <div className={`relative px-6 py-4 rounded-2xl backdrop-blur-sm ${
            isBull
              ? 'bg-gradient-to-br from-emerald-500/10 to-emerald-600/5 border border-emerald-500/20'
              : 'bg-gradient-to-br from-rose-500/10 to-rose-600/5 border border-rose-500/20'
          }`}>
            <p className={`leading-relaxed ${
              isBull ? 'text-slate-200' : 'text-slate-200'
            }`}>
              {message}
            </p>
          </div>
        </div>
      </div>

      {!isBull && (
        <div className="flex-shrink-0 relative">
          <div className="absolute inset-0 bg-rose-500 blur-lg opacity-30" />
          <div className="relative w-12 h-12 rounded-xl bg-gradient-to-br from-rose-500 to-rose-600 flex items-center justify-center shadow-lg">
            <TrendingDown className="w-6 h-6 text-white" strokeWidth={2.5} />
          </div>
        </div>
      )}
    </motion.div>
  );
}
