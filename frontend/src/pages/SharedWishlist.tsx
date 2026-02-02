import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { BookMarked } from 'lucide-react'
import { api } from '../services/api'

export default function SharedWishlist() {
  const { token } = useParams<{ token: string }>()

  const { data, isLoading, isError } = useQuery({
    queryKey: ['shared-wishlist', token],
    queryFn: () => api.getSharedWishlist(token!),
    enabled: !!token,
  })

  if (isLoading) return <div className="text-center py-20 text-slate-500">Loading wishlist...</div>
  if (isError || !data) return <div className="text-center py-20 text-slate-500">Wishlist not found or invalid link.</div>

  return (
    <div className="max-w-lg mx-auto">
      <div className="text-center mb-6">
        <BookMarked size={40} className="mx-auto text-purple-400 mb-3" />
        <h1 className="text-2xl font-bold">{data.name}</h1>
        <p className="text-slate-500 text-sm">Shared Book Wishlist</p>
      </div>

      {data.items.length === 0 ? (
        <p className="text-center text-slate-500">This wishlist is empty.</p>
      ) : (
        <div className="space-y-3">
          {data.items.map(item => (
            <div key={item.id} className="bg-slate-900 rounded-lg p-4">
              <p className="font-medium">
                {item.title || 'Untitled'}
                {item.priority >= 2 && (
                  <span className="ml-2 text-xs bg-red-900 text-red-300 px-2 py-0.5 rounded">Must have</span>
                )}
              </p>
              {item.author && <p className="text-sm text-slate-400">{item.author}</p>}
              {item.isbn && <p className="text-xs text-slate-600">ISBN: {item.isbn}</p>}
              {item.notes && <p className="text-xs text-slate-500 mt-2">{item.notes}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
