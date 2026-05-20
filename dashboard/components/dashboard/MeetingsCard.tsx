import type { UpcomingMeeting } from "@/lib/types"

interface Props {
  meetings: UpcomingMeeting[]
}

export function MeetingsCard({ meetings }: Props) {
  return (
    <div className="rounded-xl border bg-card p-5">
      <h3 className="mb-4 text-sm font-medium text-muted-foreground">
        Próximas reuniones
      </h3>
      {meetings.length === 0 ? (
        <p className="text-sm text-muted-foreground">Sin reuniones agendadas</p>
      ) : (
        <ul className="space-y-3">
          {meetings.map(m => (
            <li key={m.id} className="flex items-start gap-3">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{m.lead.name}</p>
                <p className="text-xs text-muted-foreground truncate">
                  {m.lead.company}
                </p>
                <p className="text-xs text-muted-foreground">
                  {new Date(m.scheduled_at).toLocaleString("es-CL", {
                    dateStyle: "short",
                    timeStyle: "short",
                  })}
                </p>
              </div>
              {m.meet_link && (
                <a
                  href={m.meet_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-primary hover:underline shrink-0"
                >
                  Unirse
                </a>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
