import { useState } from 'react'
import type { Radiator } from '../types'
import { setRadiatorTarget } from '../api'

export function RadiatorControl({ room, radiator }: { room: string; radiator: Radiator }) {
  const [target, setTarget] = useState<number>(radiator.target_temp ?? 20)
  const [busy, setBusy] = useState(false)

  async function adjust(delta: number) {
    const next = Math.max(5, Math.min(30, Math.round((target + delta) * 2) / 2))
    setBusy(true)
    try {
      const confirmed = await setRadiatorTarget(room, next)
      setTarget(confirmed)
    } catch (err) {
      console.error(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mt-4 border-t border-dashed border-slate-200 pt-3">
      <div className="mb-2 text-xs uppercase tracking-wide text-slate-500">Radiator</div>
      <div className="flex flex-wrap items-center gap-4">
        <span className="text-2xl font-semibold">{radiator.current_temp ?? '–'}°C</span>
        <span className="text-sm text-slate-500">
          valve {radiator.valve ?? '–'}%{radiator.mode ? ` · ${radiator.mode}` : ''}
        </span>
        <div className="inline-flex items-center gap-2">
          <button
            disabled={busy}
            onClick={() => adjust(-0.5)}
            className="h-8 w-8 rounded-md border border-slate-300 bg-white text-lg hover:bg-slate-50 disabled:opacity-50"
          >
            {'−'}
          </button>
          <span className="min-w-[92px] text-center text-sm font-semibold">Target {target}°C</span>
          <button
            disabled={busy}
            onClick={() => adjust(0.5)}
            className="h-8 w-8 rounded-md border border-slate-300 bg-white text-lg hover:bg-slate-50 disabled:opacity-50"
          >
            +
          </button>
        </div>
      </div>
    </div>
  )
}
