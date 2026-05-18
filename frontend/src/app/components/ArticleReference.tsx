import { ExternalLink, Calendar, FileText } from 'lucide-react';
import { motion } from 'motion/react';

export interface Article {
  id: string;
  title: string;
  source: string;
  date: string;
  url: string;
  referencedBy: 'bull' | 'bear' | 'both';
}

interface ArticleReferenceProps {
  article: Article;
}

export function ArticleReference({ article }: ArticleReferenceProps) {
  const getBadgeStyle = () => {
    if (article.referencedBy === 'bull') {
      return {
        bg: 'bg-emerald-500/10',
        text: 'text-emerald-400',
        border: 'border-emerald-500/30',
        glow: 'shadow-emerald-500/10'
      };
    }
    if (article.referencedBy === 'bear') {
      return {
        bg: 'bg-rose-500/10',
        text: 'text-rose-400',
        border: 'border-rose-500/30',
        glow: 'shadow-rose-500/10'
      };
    }
    return {
      bg: 'bg-blue-500/10',
      text: 'text-blue-400',
      border: 'border-blue-500/30',
      glow: 'shadow-blue-500/10'
    };
  };

  const badge = getBadgeStyle();

  return (
    <motion.a
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      href={article.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block group relative"
    >
      <div className="absolute -inset-0.5 bg-gradient-to-r from-emerald-500/0 via-emerald-500/5 to-rose-500/0 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity" />

      <div className="relative p-4 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 hover:border-white/20 transition-all backdrop-blur-sm">
        <div className="flex items-start gap-3 mb-3">
          <div className={`flex-shrink-0 w-8 h-8 rounded-lg ${badge.bg} border ${badge.border} flex items-center justify-center`}>
            <FileText className={`w-4 h-4 ${badge.text}`} />
          </div>

          <div className="flex-1 min-w-0">
            <h4 className="font-medium text-white group-hover:text-emerald-400 transition-colors line-clamp-2 leading-snug mb-2">
              {article.title}
            </h4>

            <div className="flex items-center gap-2 text-xs text-slate-500">
              <Calendar className="w-3 h-3" />
              <span className="font-mono">{article.date}</span>
              <span>•</span>
              <span className="truncate">{article.source}</span>
            </div>
          </div>

          <ExternalLink className="w-4 h-4 text-slate-600 group-hover:text-slate-400 flex-shrink-0 transition-colors" />
        </div>

        <div className={`inline-flex items-center px-2.5 py-1 rounded-lg text-xs font-medium border ${badge.bg} ${badge.text} ${badge.border} ${badge.glow} shadow-sm`}>
          {article.referencedBy === 'both' ? 'Both agents' : `${article.referencedBy.charAt(0).toUpperCase() + article.referencedBy.slice(1)} agent`}
        </div>
      </div>
    </motion.a>
  );
}
