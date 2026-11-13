import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import type { HistoryPoint } from '../types'
import { METRICS, METRIC_META } from '../constants'
import { fetchHistory } from '../api'

export function HistoryView({ rooms }: { rooms: string[] }) {
  const [room, setRoom] = useState<string>(rooms[0] ?? '')
  const [history, setHistory] = useState<HistoryPoint[]>([])

  useEffect(() => {
    if (!room && rooms.length) setRoom(rooms[0])
  }, [rooms, room])

  useEffect(() => {
    if (!room) return
    fetchHistory(room).then(setHistory).catch(console.error)
  }, [room])

  return (
    <div>
      <div className="mb-5 inline-flex flex-wrap items-center rounded-full bg-black/5 p-0.5 text-sm">
        {rooms.map((r) => (
          <button
            key={r}
            onClick={() => setRoom(r)}
            className={
              r === room
                ? 'rounded-full bg-white px-3.5 py-1 font-medium capitalize text-slate-900 shadow-sm'
                : 'rounded-full px-3.5 py-1 capitalize text-slate-500 hover:text-slate-700'
            }
          >
            {r.replace(/_/g, ' ')}
          </button>
        ))}
      </div>
      {history.length === 0 ? (
        <p className="text-slate-400">No history for this room yet.</p>
      ) : (
        METRICS.map((m) => (
          <div key={m} className="mb-5 rounded-2xl border border-black/5 bg-white/70 p-4 shadow-sm backdrop-blur-xl">
            <div className="mb-2 text-sm font-semibold tracking-tight">
              {METRIC_META[m].label} <span className="font-normal text-slate-400">({METRIC_META[m].unit})</span>
            </div>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={history}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" />
                <XAxis
                  dataKey="ts"
                  tick={{ fontSize: 11, fill: '#94a3b8' }}
                  tickFormatter={(t: string) => t.slice(11, 16)}
                  minTickGap={40}
                  stroke="#e2e8f0"
                />
                <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} width={40} stroke="#e2e8f0" />
                <Tooltip contentStyle={{ borderRadius: 12, border: '1px solid #e2e8f0', fontSize: 12 }} />
                <Line type="monotone" dataKey={m} stroke="#0071e3" strokeWidth={2} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ))
      )}
    </div>
  )
}
