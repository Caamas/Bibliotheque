import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Star, Pen, Trash2, ExternalLink, MapPin } from 'lucide-react'
import { api } from '../services/api'

export default function BookDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [editingReview, setEditingReview] = useState(false)
  const [reviewText, setReviewText] = useState('')

  const { data: book, isLoading } = useQuery({
    queryKey: ['book', id],
    queryFn: () => api.getBook(Number(id)),
    enabled: !!id,
  })

  const updateCopyMutation = useMutation({
    mutationFn: ({ copyId, data }: { copyId: number; data: Record<string, unknown> }) =>
      api.updateCopy(copyId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['book', id] })
      setEditingReview(false)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteBook(Number(id)),
    onSuccess: () => navigate('/'),
  })

  const enrichMutation = useMutation({
    mutationFn: () => api.enrichBabelio(Number(id)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['book', id] }),
  })

  if (isLoading) return <div className="text-center py-20 text-slate-500">Loading...</div>
  if (!book) return <div className="text-center py-20 text-slate-500">Book not found</div>

  const copy = book.copies?.[0]

  return (
    <div>
      <button onClick={() => navigate(-1)} className="flex items-center gap-1 text-slate-400 mb-4 hover:text-slate-200">
        <ArrowLeft size={18} /> Back
      </button>

      {/* Header */}
      <div className="flex gap-4 mb-6">
        {book.cover_url ? (
          <img src={book.cover_url} alt={book.title} className="w-32 h-48 object-cover rounded-lg shadow-lg" />
        ) : (
          <div className="w-32 h-48 bg-slate-800 rounded-lg flex items-center justify-center text-slate-600 text-xs text-center px-2">
            No cover
          </div>
        )}
        <div className="flex-1">
          <h1 className="text-xl font-bold">{book.title}</h1>
          {book.subtitle && <p className="text-slate-400">{book.subtitle}</p>}
          <p className="text-blue-400 mt-1">{book.authors?.join(', ')}</p>
          <p className="text-sm text-slate-500 mt-1">{book.publisher} {book.publication_date && `(${book.publication_date})`}</p>

          <div className="flex gap-3 mt-3 text-xs text-slate-500">
            {book.page_count && <span>{book.page_count} pages</span>}
            {book.height_mm && <span>{book.height_mm}mm height</span>}
            {book.language && <span>{book.language.toUpperCase()}</span>}
          </div>

          {book.isbn_13 && <p className="text-xs text-slate-600 mt-2">ISBN: {book.isbn_13}</p>}
        </div>
      </div>

      {/* Genre & awards */}
      <div className="flex flex-wrap gap-2 mb-4">
        {book.genre && (
          <span className="bg-blue-900/50 text-blue-300 text-xs px-3 py-1 rounded-full">{book.genre}</span>
        )}
      </div>

      {/* Copy details */}
      {copy && (
        <div className="bg-slate-900 rounded-lg p-4 mb-4">
          <h2 className="text-sm font-medium text-slate-400 mb-3">Your Copy</h2>

          <div className="grid grid-cols-2 gap-3 text-sm">
            {copy.condition && (
              <div>
                <span className="text-slate-500">Condition:</span>
                <span className="ml-2 capitalize">{copy.condition}</span>
              </div>
            )}
            {copy.purchase_location && (
              <div>
                <span className="text-slate-500">Bought at:</span>
                <span className="ml-2">{copy.purchase_location}</span>
              </div>
            )}
            {copy.purchase_date && (
              <div>
                <span className="text-slate-500">Bought:</span>
                <span className="ml-2">{copy.purchase_date}</span>
              </div>
            )}
            {copy.purchase_price != null && (
              <div>
                <span className="text-slate-500">Price:</span>
                <span className="ml-2">{copy.purchase_price} EUR</span>
              </div>
            )}
            <div>
              <span className="text-slate-500">Read:</span>
              <span className="ml-2">{copy.read_count} time{copy.read_count !== 1 ? 's' : ''}</span>
            </div>
            {copy.last_read_date && (
              <div>
                <span className="text-slate-500">Last read:</span>
                <span className="ml-2">{copy.last_read_date}</span>
              </div>
            )}
            {copy.is_signed && (
              <div className="col-span-2 flex items-center gap-2 text-amber-400">
                <Pen size={14} /> Signed by the author
              </div>
            )}
            {copy.storage_type === 'long_term' && (
              <div className="col-span-2 flex items-center gap-2 text-orange-400">
                <MapPin size={14} /> In long-term storage
              </div>
            )}
          </div>

          {/* Rating */}
          <div className="mt-4">
            <span className="text-slate-500 text-sm">Your rating: </span>
            <div className="inline-flex gap-1 ml-2">
              {[1, 2, 3, 4, 5].map(star => (
                <button
                  key={star}
                  onClick={() => {
                    const newRating = star === copy.personal_rating ? 0 : star
                    updateCopyMutation.mutate({ copyId: copy.id, data: { personal_rating: newRating } })
                  }}
                  className="hover:scale-110 transition-transform"
                >
                  <Star
                    size={20}
                    className={star <= (copy.personal_rating || 0) ? 'fill-yellow-400 text-yellow-400' : 'text-slate-600'}
                  />
                </button>
              ))}
            </div>
          </div>

          {/* Review */}
          <div className="mt-4">
            {editingReview ? (
              <div>
                <textarea
                  value={reviewText}
                  onChange={e => setReviewText(e.target.value)}
                  placeholder="Write your review..."
                  className="w-full h-32 bg-slate-800 border border-slate-700 rounded-lg p-3 text-sm focus:outline-none focus:border-blue-500"
                />
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={() => updateCopyMutation.mutate({ copyId: copy.id, data: { personal_review: reviewText } })}
                    className="px-4 py-1.5 bg-blue-600 rounded text-sm"
                  >
                    Save
                  </button>
                  <button onClick={() => setEditingReview(false)} className="px-4 py-1.5 bg-slate-700 rounded text-sm">
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div>
                {copy.personal_review ? (
                  <p className="text-sm text-slate-300 bg-slate-800 p-3 rounded-lg">{copy.personal_review}</p>
                ) : (
                  <p className="text-sm text-slate-600">No review yet</p>
                )}
                <button
                  onClick={() => { setReviewText(copy.personal_review || ''); setEditingReview(true) }}
                  className="mt-2 text-sm text-blue-400 hover:text-blue-300"
                >
                  {copy.personal_review ? 'Edit review' : 'Write a review'}
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Description */}
      {book.description && (
        <div className="mb-4">
          <h2 className="text-sm font-medium text-slate-400 mb-2">Description</h2>
          <p className="text-sm text-slate-300 leading-relaxed">{book.description}</p>
        </div>
      )}

      {/* Babelio */}
      {book.babelio_url ? (
        <a
          href={book.babelio_url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 text-sm text-purple-400 hover:text-purple-300 mb-4"
        >
          <ExternalLink size={14} /> View on Babelio
          {book.babelio_rating && <span className="text-slate-500">({book.babelio_rating}/5)</span>}
        </a>
      ) : (
        <button
          onClick={() => enrichMutation.mutate()}
          disabled={enrichMutation.isPending}
          className="text-sm text-slate-500 hover:text-slate-300 mb-4 disabled:opacity-50"
        >
          {enrichMutation.isPending ? 'Searching Babelio...' : 'Look up on Babelio'}
        </button>
      )}

      {/* Actions */}
      <div className="border-t border-slate-800 pt-4 mt-4">
        <button
          onClick={() => { if (confirm('Delete this book?')) deleteMutation.mutate() }}
          className="flex items-center gap-2 text-red-500 hover:text-red-400 text-sm"
        >
          <Trash2 size={14} /> Delete book
        </button>
      </div>
    </div>
  )
}
