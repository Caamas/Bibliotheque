import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Share2, Trash2 } from 'lucide-react'
import { api, type Wishlist } from '../services/api'

export default function Wishlists() {
  const queryClient = useQueryClient()
  const [selectedList, setSelectedList] = useState<number | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [showAddItem, setShowAddItem] = useState(false)
  const [newItem, setNewItem] = useState({ title: '', author: '', isbn: '', priority: 0, notes: '' })

  const { data: wishlists } = useQuery({
    queryKey: ['wishlists'],
    queryFn: api.listWishlists,
  })

  const { data: detail } = useQuery({
    queryKey: ['wishlist', selectedList],
    queryFn: () => api.getWishlist(selectedList!),
    enabled: selectedList != null,
  })

  const createMutation = useMutation({
    mutationFn: () => api.createWishlist(newName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wishlists'] })
      setShowCreate(false)
      setNewName('')
    },
  })

  const addItemMutation = useMutation({
    mutationFn: () => api.addWishlistItem(selectedList!, newItem),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['wishlist', selectedList] })
      setShowAddItem(false)
      setNewItem({ title: '', author: '', isbn: '', priority: 0, notes: '' })
    },
  })

  const removeItemMutation = useMutation({
    mutationFn: (itemId: number) => api.removeWishlistItem(selectedList!, itemId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['wishlist', selectedList] }),
  })

  const shareUrl = (token: string) => `${window.location.origin}/wishlist/share/${token}`

  const copyShareLink = async (token: string) => {
    try {
      await navigator.clipboard.writeText(shareUrl(token))
      alert('Share link copied!')
    } catch {
      prompt('Share link:', shareUrl(token))
    }
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-2xl font-bold">Wishlists</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1 px-3 py-2 bg-blue-600 rounded-lg text-sm"
        >
          <Plus size={16} /> New List
        </button>
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="bg-slate-900 rounded-lg p-4 mb-4 flex gap-2">
          <input
            placeholder="List name (e.g. Birthday Wishes)"
            value={newName}
            onChange={e => setNewName(e.target.value)}
            className="flex-1 px-3 py-2 bg-slate-800 border border-slate-700 rounded text-sm"
            autoFocus
          />
          <button onClick={() => createMutation.mutate()} disabled={!newName} className="px-4 py-2 bg-blue-600 rounded text-sm disabled:opacity-50">Create</button>
          <button onClick={() => setShowCreate(false)} className="px-4 py-2 bg-slate-700 rounded text-sm">Cancel</button>
        </div>
      )}

      {/* List selector */}
      <div className="flex gap-2 overflow-x-auto pb-2 mb-4">
        {wishlists?.map((wl: Wishlist) => (
          <button
            key={wl.id}
            onClick={() => setSelectedList(wl.id)}
            className={`shrink-0 px-4 py-2 rounded-lg text-sm ${
              selectedList === wl.id ? 'bg-blue-600 text-white' : 'bg-slate-900 text-slate-400'
            }`}
          >
            {wl.name} ({wl.items_count})
          </button>
        ))}
      </div>

      {/* Selected wishlist */}
      {detail && (
        <div>
          <div className="flex justify-between items-center mb-3">
            <h2 className="text-lg font-medium">{detail.name}</h2>
            <div className="flex gap-2">
              <button
                onClick={() => copyShareLink(detail.share_token)}
                className="flex items-center gap-1 px-3 py-1.5 bg-purple-700 rounded text-sm"
              >
                <Share2 size={14} /> Share
              </button>
              <button
                onClick={() => setShowAddItem(true)}
                className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 rounded text-sm"
              >
                <Plus size={14} /> Add Book
              </button>
            </div>
          </div>

          {/* Add item form */}
          {showAddItem && (
            <div className="bg-slate-900 rounded-lg p-4 mb-4">
              <div className="grid grid-cols-2 gap-3">
                <input
                  placeholder="Title"
                  value={newItem.title}
                  onChange={e => setNewItem(p => ({ ...p, title: e.target.value }))}
                  className="col-span-2 px-3 py-2 bg-slate-800 border border-slate-700 rounded text-sm"
                />
                <input
                  placeholder="Author"
                  value={newItem.author}
                  onChange={e => setNewItem(p => ({ ...p, author: e.target.value }))}
                  className="px-3 py-2 bg-slate-800 border border-slate-700 rounded text-sm"
                />
                <input
                  placeholder="ISBN (optional)"
                  value={newItem.isbn}
                  onChange={e => setNewItem(p => ({ ...p, isbn: e.target.value }))}
                  className="px-3 py-2 bg-slate-800 border border-slate-700 rounded text-sm"
                />
                <select
                  value={newItem.priority}
                  onChange={e => setNewItem(p => ({ ...p, priority: Number(e.target.value) }))}
                  className="px-3 py-2 bg-slate-800 border border-slate-700 rounded text-sm"
                >
                  <option value={0}>Normal priority</option>
                  <option value={1}>High priority</option>
                  <option value={2}>Must have!</option>
                </select>
                <input
                  placeholder="Notes"
                  value={newItem.notes}
                  onChange={e => setNewItem(p => ({ ...p, notes: e.target.value }))}
                  className="px-3 py-2 bg-slate-800 border border-slate-700 rounded text-sm"
                />
              </div>
              <div className="flex gap-2 mt-3">
                <button onClick={() => addItemMutation.mutate()} className="px-4 py-2 bg-blue-600 rounded text-sm">Add</button>
                <button onClick={() => setShowAddItem(false)} className="px-4 py-2 bg-slate-700 rounded text-sm">Cancel</button>
              </div>
            </div>
          )}

          {/* Items */}
          {detail.items.length === 0 ? (
            <p className="text-center py-8 text-slate-500">This wishlist is empty.</p>
          ) : (
            <div className="space-y-2">
              {detail.items.map(item => (
                <div key={item.id} className="flex items-center justify-between bg-slate-900 rounded-lg p-3">
                  <div>
                    <p className="font-medium">
                      {item.title || 'Untitled'}
                      {item.priority >= 2 && <span className="ml-2 text-xs bg-red-900 text-red-300 px-2 py-0.5 rounded">Must have</span>}
                      {item.priority === 1 && <span className="ml-2 text-xs bg-amber-900 text-amber-300 px-2 py-0.5 rounded">High</span>}
                    </p>
                    <p className="text-xs text-slate-500">
                      {item.author || ''}
                      {item.isbn && ` - ISBN: ${item.isbn}`}
                    </p>
                    {item.notes && <p className="text-xs text-slate-600 mt-1">{item.notes}</p>}
                  </div>
                  <button
                    onClick={() => removeItemMutation.mutate(item.id)}
                    className="text-slate-600 hover:text-red-400 p-1"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
