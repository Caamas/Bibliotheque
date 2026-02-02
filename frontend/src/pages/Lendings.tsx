import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Check, Clock } from 'lucide-react'
import { api, type Lending } from '../services/api'

export default function Lendings() {
  const queryClient = useQueryClient()

  const { data: lendings, isLoading } = useQuery({
    queryKey: ['lendings'],
    queryFn: () => api.listLendings(false),
  })

  const returnMutation = useMutation({
    mutationFn: (id: number) => api.returnLending(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['lendings'] }),
  })

  if (isLoading) return <div className="text-center py-20 text-slate-500">Loading...</div>

  const active = lendings?.filter((l: Lending) => l.is_active) || []
  const returned = lendings?.filter((l: Lending) => !l.is_active) || []

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Lent Books</h1>

      {/* Active lendings */}
      <h2 className="text-sm font-medium text-slate-400 mb-2">
        Currently Lent ({active.length})
      </h2>

      {active.length === 0 ? (
        <p className="text-slate-600 text-sm mb-6">No books currently lent out.</p>
      ) : (
        <div className="space-y-2 mb-6">
          {active.map((lending: Lending) => (
            <div
              key={lending.id}
              className={`flex items-center justify-between p-3 rounded-lg ${
                lending.is_overdue ? 'bg-red-950/40 border border-red-800' : 'bg-slate-900'
              }`}
            >
              <div>
                <p className="font-medium">{lending.borrower_name}</p>
                <p className="text-xs text-slate-500">
                  Since {lending.lent_date}
                  {lending.expected_return_date && ` - Due: ${lending.expected_return_date}`}
                </p>
                {lending.is_overdue && (
                  <p className="text-xs text-red-400 flex items-center gap-1 mt-1">
                    <AlertTriangle size={12} /> Overdue
                  </p>
                )}
              </div>
              <button
                onClick={() => returnMutation.mutate(lending.id)}
                className="flex items-center gap-1 px-3 py-1.5 bg-green-700 hover:bg-green-600 rounded text-sm"
              >
                <Check size={14} /> Returned
              </button>
            </div>
          ))}
        </div>
      )}

      {/* History */}
      {returned.length > 0 && (
        <>
          <h2 className="text-sm font-medium text-slate-400 mb-2">
            History ({returned.length})
          </h2>
          <div className="space-y-1">
            {returned.slice(0, 20).map((lending: Lending) => (
              <div key={lending.id} className="flex items-center gap-2 p-2 text-sm text-slate-500">
                <Clock size={14} />
                <span>{lending.borrower_name}</span>
                <span className="text-slate-700">
                  {lending.lent_date} - {lending.actual_return_date}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
