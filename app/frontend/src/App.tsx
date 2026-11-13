import { useEffect, useState } from 'react'
import type { Room } from './types'
import { fetchRooms } from './api'
import { RoomCard } from './components/RoomCard'
import { HistoryView } from './components/HistoryView'

type Tab = 'dashboard' | 'history'

export default function App() {
  const [rooms, setRooms] = useState<Room[]>([])
  const [tab, setTab] = useState<Tab>('dashboard')
  const [error, setError] = useState<string | null>(null)

  async function load() {
    try {
      setRooms(await fetchRooms())
      setError(null)
    } catch (err) {
      setError('Could not load data. Is the backend running?')
    }
  }

  useEffect(() => {
    load()
    const id = setInterval(load, 15000)
    return () => clearInterval(id)
  }, [])

  const roomNames = rooms.map((r) => r.room)

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white px-6 py-5">
        <h1 className="text-xl font-semibold">Home Climate Control</h1>
        <p className="mt-1 text-sm text-slate-500">Live indoor air quality and heating, per room</p>
        <nav className="mt-3 flex gap-4 text-sm">
          <button onClick={() => setTab('dashboard')} className={tab === 'dashboard' ? 'font-semibold' : 'text-blue-600'}>
            Dashboard
          </button>
          <button onClick={() => setTab('history')} className={tab === 'history' ? 'font-semibold' : 'text-blue-600'}>
            History
          </button>
        </nav>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-6">
        {error && (
          <div className="mb-4 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-700">{error}</div>
        )}
        {tab === 'dashboard' ? (
          rooms.length ? (
            rooms.map((r) => <RoomCard key={r.room} room={r} />)
          ) : (
            <p className="text-slate-500">Waiting for sensor data…</p>
          )
        ) : (
          <HistoryView rooms={roomNames} />
        )}
      </main>
    </div>
  )
}
