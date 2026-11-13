import type { Metric, Status } from '../types'
import { METRIC_META, STATUS_CLASSES } from '../constants'

export function MetricTile({ metric, value, status }: { metric: Metric; value: number | null; status: Status }) {
  const meta = METRIC_META[metric]
  return (
    <div className={`rounded-xl border p-3 ${STATUS_CLASSES[status]}`}>
      <div className="text-[11px] font-medium uppercase tracking-wide opacity-70">{meta.label}</div>
      <div className="mt-1 text-2xl font-semibold tracking-tight">
        {value ?? '–'} <span className="text-xs font-normal opacity-60">{meta.unit}</span>
      </div>
    </div>
  )
}
