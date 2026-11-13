import type { Metric, Status } from './types'

export const METRICS: Metric[] = ['co2', 'pm25', 'voc', 'temperature', 'humidity']

export const METRIC_META: Record<Metric, { label: string; unit: string }> = {
  co2: { label: 'CO₂', unit: 'ppm' },
  pm25: { label: 'PM2.5', unit: 'µg/m³' },
  voc: { label: 'VOC', unit: 'index' },
  temperature: { label: 'Temperature', unit: '°C' },
  humidity: { label: 'Humidity', unit: '%' },
}

export const STATUS_CLASSES: Record<Status, string> = {
  good: 'bg-emerald-50 border-emerald-500 text-emerald-700',
  moderate: 'bg-amber-50 border-amber-500 text-amber-700',
  poor: 'bg-red-50 border-red-500 text-red-700',
  unknown: 'bg-slate-50 border-slate-400 text-slate-600',
}
