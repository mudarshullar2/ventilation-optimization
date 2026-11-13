import type { Room } from '../types'
import { METRICS } from '../constants'
import { MetricTile } from './MetricTile'
import { InsightsPanel } from './InsightsPanel'
import { RadiatorControl } from './RadiatorControl'

export function RoomCard({ room }: { room: Room }) {
  return (
    <div className="mb-6 rounded-2xl border border-black/5 bg-white/70 p-5 shadow-sm backdrop-blur-xl">
      <h2 className="mb-4 text-[15px] font-semibold capitalize tracking-tight">{room.room.replace(/_/g, ' ')}</h2>
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
