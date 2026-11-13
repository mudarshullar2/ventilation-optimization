import type { Metric, Status } from '../types'
import { METRIC_META, STATUS_CLASSES } from '../constants'

export function MetricTile({ metric, value, status }: { metric: Metric; value: number | null; status: Status }) {
  const meta = METRIC_META[metric]
  return (
    <div className={`rounded-lg border p-3 ${STATUS_CLASSES[status]}`}>
      <div className="text-xs opacity-70">{meta.label}</div>
      <div className="mt-1 text-2xl font-semibold">
        {value ?? '–'} <span className="text-xs font-normal opacity-70">{meta.unit}</span>
      </div>
    </div>
  )
}
