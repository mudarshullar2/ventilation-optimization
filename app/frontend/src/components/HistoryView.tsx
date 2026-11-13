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
      <div className="mb-4 flex flex-wrap gap-3">
        {rooms.map((r) => (
          <button
            key={r}
            onClick={() => setRoom(r)}
            className={`text-sm capitalize ${r === room ? 'font-bold text-slate-900' : 'text-blue-600'}`}
          >
            {r.replace(/_/g, ' ')}
          </button>
        ))}
      </div>
      {history.length === 0 ? (
        <p className="text-slate-500">No history for this room yet.</p>
      ) : (
        METRICS.map((m) => (
          <div key={m} className="mb-4 rounded-xl border border-slate-200 bg-white p-3">
            <div className="mb-2 text-sm font-semibold">
              {METRIC_META[m].label} ({METRIC_META[m].unit})
            </div>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={history}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" />
                <XAxis
                  dataKey="ts"
                  tick={{ fontSize: 11 }}
                  tickFormatter={(t: string) => t.slice(11, 16)}
                  minTickGap={40}
                />
                <YAxis tick={{ fontSize: 11 }} width={40} />
                <Tooltip />
                <Line type="monotone" dataKey={m} stroke="#1a73e8" dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ))
      )}
    </div>
  )
}
