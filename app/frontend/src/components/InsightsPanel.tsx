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
    <div className="mt-4 border-t border-dashed border-slate-200 pt-3">
      <div className="mb-2 text-xs uppercase tracking-wide text-slate-500">Insights</div>
      {anomalies.map((m) => (
        <span
          key={m}
          className="mr-2 mb-1 inline-block rounded border border-red-500 bg-red-50 px-2 py-0.5 text-xs font-semibold text-red-700"
        >
          {'⚠'} {METRIC_META[m].label} anomaly
        </span>
      ))}
      <div className="text-sm">
        {METRICS.map((m) => {
          const f = insight.forecast?.[m]
          if (!f) return null
          return (
            <span key={m} className="mr-4 whitespace-nowrap">
              {METRIC_META[m].label}: {ARROW[f.trend]} {f.predicted} {METRIC_META[m].unit}{' '}
              <span className="text-slate-400">(+{f.horizon_min}m)</span>
            </span>
          )
        })}
      </div>
      {insight.summary && <div className="mt-2 text-sm italic text-slate-600">{insight.summary}</div>}
    </div>
  )
}
