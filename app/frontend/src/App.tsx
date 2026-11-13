import { useEffect, useState } from 'react'
import type { Room } from './types'
import { fetchRooms, fetchMe, logout, type Me } from './api'
import { RoomCard } from './components/RoomCard'
import { HistoryView } from './components/HistoryView'
import { Login } from './components/Login'

type Tab = 'dashboard' | 'history'

function seg(active: boolean) {
  return active
    ? 'rounded-full bg-white px-3.5 py-1 font-medium text-slate-900 shadow-sm'
    : 'rounded-full px-3.5 py-1 text-slate-500 hover:text-slate-700'
}

export default function App() {
  const [me, setMe] = useState<Me | null>(null)
  const [rooms, setRooms] = useState<Room[]>([])
  const [tab, setTab] = useState<Tab>('dashboard')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchMe().then(setMe).catch(() => setMe({ authenticated: false }))
  }, [])

  async function load() {
    try {
      setRooms(await fetchRooms())
      setError(null)
    } catch (err) {
      setError('Could not load data. Is the backend running?')
    }
  }

  useEffect(() => {
    if (!me?.authenticated) return
    load()
    const id = setInterval(load, 15000)
    return () => clearInterval(id)
  }, [me])

  if (me === null) {
    return <div className="flex min-h-screen items-center justify-center text-slate-400">Loading…</div>
  }

  if (!me.authenticated) {
    return <Login onSuccess={() => fetchMe().then(setMe)} />
  }

  const roomNames = rooms.map((r) => r.room)

  async function doLogout() {
    await logout()
    setMe({ authenticated: false })
    setRooms([])
  }

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-black/5 bg-white/70 backdrop-blur-xl">
        <div className="mx-auto flex max-w-5xl items-center gap-4 px-6 py-3">
          <div className="flex gap-2">
            <span className="h-3 w-3 rounded-full bg-[#ff5f57]" />
            <span className="h-3 w-3 rounded-full bg-[#febc2e]" />
            <span className="h-3 w-3 rounded-full bg-[#28c840]" />
          </div>
          <h1 className="flex-1 text-sm font-semibold tracking-tight">Home Climate Control</h1>
          <div className="inline-flex items-center rounded-full bg-black/5 p-0.5 text-sm">
            <button className={seg(tab === 'dashboard')} onClick={() => setTab('dashboard')}>Dashboard</button>
            <button className={seg(tab === 'history')} onClick={() => setTab('history')}>History</button>
          </div>
          <span className="text-sm text-slate-500">{me.username}</span>
          <button onClick={doLogout} className="text-sm text-blue-600 hover:text-blue-700">Sign out</button>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-8">
        {error && (
          <div className="mb-4 rounded-2xl border border-red-200 bg-red-50/80 p-3 text-sm text-red-700 backdrop-blur">
            {error}
          </div>
        )}
        {tab === 'dashboard' ? (
          rooms.length ? (
            rooms.map((r) => <RoomCard key={r.room} room={r} />)
          ) : (
            <p className="text-slate-400">Waiting for sensor data…</p>
          )
        ) : (
          <HistoryView rooms={roomNames} />
        )}
      </main>
    </div>
  )
}
