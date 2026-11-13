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
      setTarget(await setRadiatorTarget(room, next))
    } catch (err) {
      console.error(err)
    } finally {
      setBusy(false)
    }
  }

  const btn =
    'flex h-9 w-9 items-center justify-center rounded-full border border-black/10 bg-white text-lg shadow-sm transition active:scale-95 hover:bg-slate-50 disabled:opacity-50'

  return (
    <div className="mt-4 border-t border-black/5 pt-4">
      <div className="mb-2 text-[11px] font-medium uppercase tracking-wide text-slate-400">Radiator</div>
      <div className="flex flex-wrap items-center gap-5">
        <span className="text-2xl font-semibold tracking-tight">{radiator.current_temp ?? '–'}°C</span>
        <span className="text-sm text-slate-400">
          valve {radiator.valve ?? '–'}%{radiator.mode ? ` · ${radiator.mode}` : ''}
        </span>
        <div className="ml-auto inline-flex items-center gap-3">
          <button disabled={busy} onClick={() => adjust(-0.5)} className={btn} aria-label="Lower target">−</button>
          <span className="min-w-[96px] text-center text-sm font-semibold">Target {target}°C</span>
          <button disabled={busy} onClick={() => adjust(0.5)} className={btn} aria-label="Raise target">+</button>
        </div>
      </div>
    </div>
  )
}
