import type { Room } from '../types'
import { METRICS } from '../constants'
import { MetricTile } from './MetricTile'
import { InsightsPanel } from './InsightsPanel'
import { RadiatorControl } from './RadiatorControl'

export function RoomCard({ room }: { room: Room }) {
  return (
    <div className="mb-5 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="mb-3 text-base font-semibold capitalize">{room.room.replace(/_/g, ' ')}</h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {METRICS.map((m) => (
          <MetricTile key={m} metric={m} value={room.readings[m]} status={room.status[m]} />
        ))}
      </div>
      {room.insight && <InsightsPanel insight={room.insight} />}
      {room.radiator && <RadiatorControl room={room.room} radiator={room.radiator} />}
    </div>
  )
}
