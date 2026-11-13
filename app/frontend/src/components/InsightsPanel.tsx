import type { Insight } from '../types'
import { METRICS, METRIC_META } from '../constants'

const ARROW: Record<'rising' | 'falling' | 'stable', string> = {
  rising: '↗',
  falling: '↘',
  stable: '→',
}

export function InsightsPanel({ insight }: { insight: Insight }) {
  const anomalies = METRICS.filter((m) => insight.anomalies?.[m]?.anomaly)
  return (
    <div className="mt-4 border-t border-black/5 pt-4">
      <div className="mb-2 text-[11px] font-medium uppercase tracking-wide text-slate-400">Insights</div>
      {anomalies.map((m) => (
        <span
          key={m}
          className="mr-2 mb-1 inline-block rounded-full border border-red-200 bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-600"
        >
          ⚠ {METRIC_META[m].label} anomaly
        </span>
      ))}
      <div className="text-sm text-slate-600">
        {METRICS.map((m) => {
          const f = insight.forecast?.[m]
          if (!f) return null
          return (
            <span key={m} className="mr-4 whitespace-nowrap">
              {METRIC_META[m].label}: {ARROW[f.trend]} {f.predicted} {METRIC_META[m].unit}{' '}
              <span className="text-slate-300">(+{f.horizon_min}m)</span>
            </span>
          )
        })}
      </div>
      {insight.summary && <div className="mt-2 text-sm italic text-slate-500">{insight.summary}</div>}
    </div>
  )
}
