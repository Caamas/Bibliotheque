import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Sparkles, AlertTriangle, BarChart3 } from 'lucide-react'
import { api, type OptimizeResult } from '../services/api'

export default function Optimizer() {
  const [sortOrder, setSortOrder] = useState('author')
  const [includeStorage, setIncludeStorage] = useState(false)
  const [result, setResult] = useState<OptimizeResult | null>(null)

  const optimizeMutation = useMutation({
    mutationFn: () => api.optimize({ sort_order: sortOrder, include_long_term_storage: includeStorage }),
    onSuccess: (data) => setResult(data),
  })

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Shelf Optimizer</h1>

      <p className="text-slate-400 text-sm mb-6">
        Analyze your book collection and calculate the optimal shelf arrangement
        to minimize wasted vertical space. Books are grouped by height and assigned
        to shelves for maximum efficiency.
      </p>

      {/* Settings */}
      <div className="bg-slate-900 rounded-lg p-4 mb-6">
        <h3 className="font-medium mb-3">Optimization Settings</h3>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-sm text-slate-400 block mb-1">Sort books by</label>
            <select
              value={sortOrder}
              onChange={e => setSortOrder(e.target.value)}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded text-sm"
            >
              <option value="author">Author</option>
              <option value="genre">Genre</option>
              <option value="publisher">Publisher</option>
              <option value="title">Title</option>
              <option value="last_read">Last Read</option>
            </select>
          </div>
          <div className="flex items-end">
            <label className="flex items-center gap-2 text-sm pb-2">
              <input
                type="checkbox"
                checked={includeStorage}
                onChange={e => setIncludeStorage(e.target.checked)}
                className="rounded"
              />
              Include long-term storage
            </label>
          </div>
        </div>

        <button
          onClick={() => optimizeMutation.mutate()}
          disabled={optimizeMutation.isPending}
          className="mt-4 w-full py-3 bg-gradient-to-r from-purple-600 to-blue-600 rounded-lg font-medium flex items-center justify-center gap-2 disabled:opacity-50"
        >
          <Sparkles size={18} />
          {optimizeMutation.isPending ? 'Optimizing...' : 'Run Optimization'}
        </button>
      </div>

      {/* Error */}
      {optimizeMutation.isError && (
        <div className="bg-red-950/50 border border-red-800 rounded-lg p-4 mb-4">
          <p className="text-red-300">
            {(optimizeMutation.error as Error).message || 'Optimization failed. Make sure you have books and shelves configured.'}
          </p>
        </div>
      )}

      {/* Results */}
      {result && (
        <div>
          {/* Summary */}
          <div className="grid grid-cols-3 gap-3 mb-6">
            <div className="bg-slate-900 rounded-lg p-4 text-center">
              <p className="text-2xl font-bold text-blue-400">{result.total_books}</p>
              <p className="text-xs text-slate-500">Total Books</p>
            </div>
            <div className="bg-slate-900 rounded-lg p-4 text-center">
              <p className="text-2xl font-bold text-green-400">{result.assigned_count}</p>
              <p className="text-xs text-slate-500">Assigned</p>
            </div>
            <div className="bg-slate-900 rounded-lg p-4 text-center">
              <p className="text-2xl font-bold text-orange-400">{result.unassigned_count}</p>
              <p className="text-xs text-slate-500">Unassigned</p>
            </div>
          </div>

          {/* Warnings */}
          {result.warnings.length > 0 && (
            <div className="bg-amber-950/50 border border-amber-800 rounded-lg p-3 mb-4">
              {result.warnings.map((w, i) => (
                <p key={i} className="text-sm text-amber-300 flex items-center gap-2">
                  <AlertTriangle size={14} /> {w}
                </p>
              ))}
            </div>
          )}

          {/* Height clusters */}
          <h3 className="font-medium mb-2 flex items-center gap-2">
            <BarChart3 size={18} /> Height Clusters
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mb-6">
            {result.clusters.map(cluster => (
              <div key={cluster.name} className="bg-slate-900 rounded-lg p-3">
                <p className="font-medium capitalize text-sm">{cluster.name.replace('_', ' ')}</p>
                <p className="text-xs text-slate-500">
                  {cluster.min_height}-{cluster.max_height}mm
                </p>
                <p className="text-lg font-bold text-blue-400">{cluster.books_count}</p>
                <p className="text-xs text-slate-500">
                  Needs {cluster.required_shelf_height}mm shelf height
                </p>
              </div>
            ))}
          </div>

          {/* Shelf utilization */}
          <h3 className="font-medium mb-2">Shelf Utilization</h3>
          <div className="space-y-2 mb-6">
            {result.shelf_utilization.map(shelf => (
              <div key={shelf.shelf_id} className="bg-slate-900 rounded-lg p-3">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-sm">Shelf #{shelf.shelf_id}</span>
                  <span className="text-sm text-slate-400">{shelf.books_count} books</span>
                </div>
                <div className="w-full bg-slate-800 rounded-full h-2">
                  <div
                    className="bg-blue-500 h-2 rounded-full"
                    style={{ width: `${Math.min(100, shelf.width_utilization_pct)}%` }}
                  />
                </div>
                <p className="text-xs text-slate-500 mt-1">
                  {shelf.width_utilization_pct}% width used
                  {shelf.height_wasted_mm > 0 && ` - ${shelf.height_wasted_mm}mm height wasted`}
                </p>
              </div>
            ))}
          </div>

          {/* Assignments (collapsed by default) */}
          <details className="mb-6">
            <summary className="cursor-pointer font-medium mb-2">
              View All Assignments ({result.assignments.length})
            </summary>
            <div className="space-y-1 max-h-96 overflow-y-auto">
              {result.assignments.map((a, i) => (
                <div key={i} className="flex justify-between text-sm bg-slate-900 rounded px-3 py-1.5">
                  <span className="truncate flex-1">{a.book_title}</span>
                  <span className="text-slate-500 ml-2 shrink-0">
                    Shelf #{a.shelf_id} pos {a.position}
                  </span>
                </div>
              ))}
            </div>
          </details>
        </div>
      )}

      {/* How it works */}
      <div className="bg-slate-900 rounded-lg p-4 text-sm text-slate-400">
        <h3 className="font-medium text-slate-300 mb-2">How It Works</h3>
        <ol className="space-y-1 list-decimal list-inside">
          <li>Books are grouped into height clusters (pocket, standard, large, etc.)</li>
          <li>Each cluster is assigned to shelves that can accommodate the tallest book</li>
          <li>Books are packed by width, minimizing wasted horizontal space</li>
          <li>Within each shelf, books are sorted by your preferred order</li>
          <li>Adjustable shelves get recommended height settings</li>
        </ol>
      </div>
    </div>
  )
}
