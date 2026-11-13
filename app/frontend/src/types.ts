export type Metric = 'co2' | 'pm25' | 'voc' | 'temperature' | 'humidity'
export type Status = 'good' | 'moderate' | 'poor' | 'unknown'

export interface Forecast {
  horizon_min: number
  predicted: number
  trend: 'rising' | 'falling' | 'stable'
}
export interface Anomaly {
  anomaly: boolean
  score: number
}
export interface Insight {
  generated_at?: string
  forecast: Partial<Record<Metric, Forecast>>
  anomalies: Partial<Record<Metric, Anomaly>>
  summary: string
}
export interface Radiator {
  current_temp: number | null
  target_temp: number | null
  valve: number | null
  mode: string | null
  timestamp?: string
}
export interface Room {
  room: string
  timestamp: string | null
  readings: Record<Metric, number | null>
  status: Record<Metric, Status>
  insight: Insight | null
  radiator: Radiator | null
}
export interface HistoryPoint {
  ts: string
  co2: number | null
  pm25: number | null
  voc: number | null
  temperature: number | null
  humidity: number | null
}
