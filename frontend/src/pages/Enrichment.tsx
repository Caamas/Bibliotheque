import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Download, Check, X, Loader2, BarChart3, Play } from 'lucide-react'
import { api, type EnrichmentStats, type EnrichmentResults } from '../services/api'

export default function Enrichment() {
  const queryClient = useQueryClient()
  const [reviewIndex, setReviewIndex] = useState(0)
  const [acceptedFields, setAcceptedFields] = useState<Record<string, boolean>>({})

  const { data: stats } = useQuery<EnrichmentStats>({
    queryKey: ['enrichment-stats'],
    queryFn: () => api.getEnrichmentStats(),
  })

  const { data: status } = useQuery({
    queryKey: ['enrichment-status'],
    queryFn: () => api.getEnrichmentStatus(),
    refetchInterval: (query) => query.state.data?.running ? 2000 : false,
  })

  const { data: results } = useQuery<EnrichmentResults>({
    queryKey: ['enrichment-results'],
    queryFn: () => api.getEnrichmentResults(),
    enabled: status?.has_results === true,
  })

  const startJob = useMutation({
    mutationFn: () => api.startEnrichment(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['enrichment-status'] }),
  })

  const applyOne = useMutation({
    mutationFn: (data: { book_id: number; accepted_fields: Record<string, unknown> }) =>
      api.applyEnrichment(data.book_id, data.accepted_fields),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['enrichment-stats'] })
      setReviewIndex(prev => prev + 1)
      setAcceptedFields({})
    },
  })

  const currentProposal = results?.proposals[reviewIndex]

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold flex items-center gap-2">
        <Download size={24} />
        Batch Enrichment
      </h1>

      {/* Stats */}
      {stats && (
        <div className="bg-slate-900 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-3">
            <BarChart3 size={18} className="text-blue-400" />
            <span className="font-medium">Collection Completeness</span>
            <span className="ml-auto text-blue-400 font-bold">{stats.completeness_pct}%</span>
          </div>
          <div className="w-full bg-slate-700 rounded-full h-2 mb-3">
            <div className="bg-blue-500 h-2 rounded-full" style={{ width: `${stats.completeness_pct}%` }} />
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs text-slate-400">
            <div>Total books: <span className="text-white">{stats.total_books}</span></div>
            <div>With ISBN: <span className="text-white">{stats.with_isbn}</span></div>
            <div>With height: <span className="text-white">{stats.with_height}</span></div>
            <div>With cover: <span className="text-white">{stats.with_cover}</span></div>
          </div>
        </div>
      )}

      {/* Job control */}
      <div className="bg-slate-900 rounded-lg p-4">
        {status?.running ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Loader2 size={18} className="animate-spin text-blue-400" />
              <span>Enriching books from APIs...</span>
              <span className="ml-auto text-sm text-slate-400">
                {status.progress}/{status.total}
              </span>
            </div>
            <div className="w-full bg-slate-700 rounded-full h-2">
              <div
                className="bg-blue-500 h-2 rounded-full transition-all"
                style={{ width: `${status.total ? (status.progress / status.total) * 100 : 0}%` }}
              />
            </div>
          </div>
        ) : (
          <button
            onClick={() => startJob.mutate()}
            disabled={startJob.isPending}
            className="w-full py-3 bg-blue-600 hover:bg-blue-700 rounded-lg flex items-center justify-center gap-2"
          >
            <Play size={18} />
            Start Batch Enrichment
          </button>
        )}
        <p className="text-xs text-slate-500 mt-2">
          Queries Open Library & Google Books for all books with ISBN that have missing metadata.
          Rate-limited to ~40 requests/minute.
        </p>
      </div>

      {/* Review proposals */}
      {results && results.proposals.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-medium">Review Proposals</h2>
            <span className="text-sm text-slate-400">
              {reviewIndex + 1} / {results.proposals.length}
            </span>
          </div>

          {currentProposal ? (
            <div className="bg-slate-900 rounded-lg p-4 space-y-3">
              <p className="font-medium">{currentProposal.title}</p>
              <p className="text-xs text-slate-500">ISBN: {currentProposal.isbn}</p>

              {Object.entries(currentProposal.proposals).map(([field, data]) => (
                <div key={field} className="border border-slate-700 rounded p-2">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium text-slate-400 capitalize">
                      {field.replace('_', ' ')}
                    </span>
                    <button
                      onClick={() => setAcceptedFields(prev => ({ ...prev, [field]: !prev[field] }))}
                      className={`p-1 rounded ${acceptedFields[field] ? 'bg-green-600' : 'bg-slate-700'}`}
                    >
                      <Check size={14} />
                    </button>
                  </div>
                  {data.current != null && (
                    <p className="text-xs text-red-400 line-through">
                      {typeof data.current === 'object' ? JSON.stringify(data.current) : String(data.current)}
                    </p>
                  )}
                  <p className="text-sm text-green-400">
                    {typeof data.proposed === 'object' ? JSON.stringify(data.proposed) : String(data.proposed)}
                  </p>
                  <p className="text-xs text-slate-600">Source: {data.source}</p>
                </div>
              ))}

              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => {
                    setReviewIndex(prev => prev + 1)
                    setAcceptedFields({})
                  }}
                  className="flex-1 py-2 bg-slate-700 rounded flex items-center justify-center gap-1 text-sm"
                >
                  <X size={16} /> Skip
                </button>
                <button
                  onClick={() => {
                    const fields: Record<string, unknown> = {}
                    for (const [field, accepted] of Object.entries(acceptedFields)) {
                      if (accepted && currentProposal.proposals[field]) {
                        fields[field] = currentProposal.proposals[field].proposed
                      }
                    }
                    if (Object.keys(fields).length > 0) {
                      applyOne.mutate({ book_id: currentProposal.book_id, accepted_fields: fields })
                    }
                  }}
                  disabled={!Object.values(acceptedFields).some(Boolean)}
                  className="flex-1 py-2 bg-green-600 hover:bg-green-700 disabled:bg-slate-700 rounded flex items-center justify-center gap-1 text-sm"
                >
                  <Check size={16} /> Apply Selected
                </button>
              </div>

              {/* Accept all shortcut */}
              <button
                onClick={() => {
                  const fields: Record<string, unknown> = {}
                  for (const [field, data] of Object.entries(currentProposal.proposals)) {
                    fields[field] = data.proposed
                  }
                  applyOne.mutate({ book_id: currentProposal.book_id, accepted_fields: fields })
                }}
                className="w-full py-2 border border-green-600 text-green-400 rounded text-sm hover:bg-green-600/10"
              >
                Accept All Fields
              </button>
            </div>
          ) : (
            <div className="text-center py-8 text-slate-500">
              All proposals reviewed! {results.enriched} books enriched.
            </div>
          )}
        </div>
      )}

      {results && results.proposals.length === 0 && (
        <div className="text-center py-8 text-slate-500">
          No new metadata found. Your collection might already be complete,
          or the books could not be found in online databases.
        </div>
      )}
    </div>
  )
}
