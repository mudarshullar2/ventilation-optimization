import type { Room, HistoryPoint } from './types'

let csrf: string | null = null

async function getCsrf(): Promise<string> {
  if (csrf) return csrf
  const r = await fetch('/api/csrf-token')
  const d = await r.json()
  csrf = d.csrf_token as string
  return csrf
}

export async function fetchRooms(): Promise<Room[]> {
  const r = await fetch('/api/rooms')
  if (!r.ok) throw new Error('failed to load rooms')
  const d = await r.json()
  return d.rooms as Room[]
}

export async function fetchHistory(room: string, hours = 24): Promise<HistoryPoint[]> {
  const r = await fetch(`/api/history?room=${encodeURIComponent(room)}&hours=${hours}`)
  if (!r.ok) throw new Error('failed to load history')
  const d = await r.json()
  return d.history as HistoryPoint[]
}

export async function setRadiatorTarget(room: string, target: number): Promise<number> {
  const token = await getCsrf()
  const r = await fetch(`/api/radiator/${encodeURIComponent(room)}/set`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token },
    body: JSON.stringify({ target_temp: target }),
  })
  if (!r.ok) throw new Error('failed to set target')
  const d = await r.json()
  return d.target_temp as number
}
