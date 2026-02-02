import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Search, ChevronLeft, ChevronRight } from 'lucide-react'
import { api, type Book } from '../services/api'

export default function Library() {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [sortBy, setSortBy] = useState('title')

  const { data, isLoading } = useQuery({
    queryKey: ['books', { search, page, sortBy }],
    queryFn: () => api.listBooks({ search, page: String(page), page_size: '50', sort_by: sortBy }),
  })

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 0

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">My Library</h1>

      {/* Search & filters */}
      <div className="flex gap-2 mb-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-2.5 text-slate-500" size={18} />
          <input
            type="text"
            placeholder="Search by title, ISBN..."
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1) }}
            className="w-full pl-10 pr-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm focus:outline-none focus:border-blue-500"
          />
        </div>
        <select
          value={sortBy}
          onChange={e => setSortBy(e.target.value)}
          className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm"
        >
          <option value="title">Title</option>
          <option value="created_at">Recently added</option>
          <option value="genre">Genre</option>
          <option value="publisher">Publisher</option>
        </select>
      </div>

      {/* Stats */}
      {data && (
        <p className="text-slate-500 text-sm mb-4">
          {data.total} book{data.total !== 1 ? 's' : ''} in collection
        </p>
      )}

      {/* Book grid */}
      {isLoading ? (
        <div className="text-center py-20 text-slate-500">Loading...</div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
          {data?.items.map((book: Book) => (
            <Link
              key={book.id}
              to={`/book/${book.id}`}
              className="bg-slate-900 rounded-lg overflow-hidden hover:ring-1 hover:ring-blue-500 transition-all"
            >
              {book.cover_url ? (
                <img
                  src={book.cover_url}
                  alt={book.title}
                  className="w-full h-48 object-cover"
                  loading="lazy"
                />
              ) : (
                <div className="w-full h-48 bg-slate-800 flex items-center justify-center text-slate-600 text-xs px-2 text-center">
                  {book.title}
                </div>
              )}
              <div className="p-2">
                <p className="text-sm font-medium truncate">{book.title}</p>
                <p className="text-xs text-slate-400 truncate">
                  {book.authors?.join(', ') || 'Unknown author'}
                </p>
                {book.genre && (
                  <span className="inline-block mt-1 text-xs bg-slate-800 text-slate-400 px-2 py-0.5 rounded">
                    {book.genre}
                  </span>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* Empty state */}
      {data?.items.length === 0 && !isLoading && (
        <div className="text-center py-20">
          <p className="text-slate-500 mb-4">No books yet. Start scanning!</p>
          <Link to="/scan" className="text-blue-400 hover:text-blue-300">
            Go to Scanner
          </Link>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center items-center gap-4 mt-6">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            className="p-2 rounded-lg bg-slate-900 disabled:opacity-30"
          >
            <ChevronLeft size={20} />
          </button>
          <span className="text-sm text-slate-400">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="p-2 rounded-lg bg-slate-900 disabled:opacity-30"
          >
            <ChevronRight size={20} />
          </button>
        </div>
      )}
    </div>
  )
}
