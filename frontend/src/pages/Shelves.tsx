import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, ChevronDown, ChevronRight } from 'lucide-react'
import { api, type Bookcase } from '../services/api'

export default function Shelves() {
  const queryClient = useQueryClient()
  const [expandedBookcase, setExpandedBookcase] = useState<number | null>(null)
  const [showAddBookcase, setShowAddBookcase] = useState(false)
  const [newBookcase, setNewBookcase] = useState({ name: '', room: '', total_height_mm: '', total_width_mm: '', adjustable_shelves: true })
  const [showAddShelf, setShowAddShelf] = useState<number | null>(null)
  const [newShelf, setNewShelf] = useState({ shelf_number: 1, usable_height_mm: '', usable_width_mm: '' })

  const { data: bookcases, isLoading } = useQuery({
    queryKey: ['bookcases'],
    queryFn: api.listBookcases,
  })

  const { data: bookcaseDetail } = useQuery({
    queryKey: ['bookcase', expandedBookcase],
    queryFn: () => api.getBookcase(expandedBookcase!),
    enabled: expandedBookcase != null,
  })

  const addBookcaseMutation = useMutation({
    mutationFn: () => api.createBookcase({
      name: newBookcase.name,
      room: newBookcase.room || undefined,
      total_height_mm: newBookcase.total_height_mm ? Number(newBookcase.total_height_mm) : undefined,
      total_width_mm: newBookcase.total_width_mm ? Number(newBookcase.total_width_mm) : undefined,
      adjustable_shelves: newBookcase.adjustable_shelves,
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bookcases'] })
      setShowAddBookcase(false)
      setNewBookcase({ name: '', room: '', total_height_mm: '', total_width_mm: '', adjustable_shelves: true })
    },
  })

  const addShelfMutation = useMutation({
    mutationFn: (bookcaseId: number) => api.createShelf({
      bookcase_id: bookcaseId,
      shelf_number: newShelf.shelf_number,
      usable_height_mm: Number(newShelf.usable_height_mm),
      usable_width_mm: Number(newShelf.usable_width_mm),
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bookcase', expandedBookcase] })
      setShowAddShelf(null)
      setNewShelf({ shelf_number: 1, usable_height_mm: '', usable_width_mm: '' })
    },
  })

  if (isLoading) return <div className="text-center py-20 text-slate-500">Loading...</div>

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-2xl font-bold">Bookshelves</h1>
        <button
          onClick={() => setShowAddBookcase(true)}
          className="flex items-center gap-1 px-3 py-2 bg-blue-600 rounded-lg text-sm"
        >
          <Plus size={16} /> Add Bookcase
        </button>
      </div>

      {/* Add bookcase form */}
      {showAddBookcase && (
        <div className="bg-slate-900 rounded-lg p-4 mb-4">
          <h3 className="font-medium mb-3">New Bookcase</h3>
          <div className="grid grid-cols-2 gap-3">
            <input
              placeholder="Name (e.g. Living Room Left)"
              value={newBookcase.name}
              onChange={e => setNewBookcase(p => ({ ...p, name: e.target.value }))}
              className="col-span-2 px-3 py-2 bg-slate-800 border border-slate-700 rounded text-sm"
            />
            <input
              placeholder="Room"
              value={newBookcase.room}
              onChange={e => setNewBookcase(p => ({ ...p, room: e.target.value }))}
              className="px-3 py-2 bg-slate-800 border border-slate-700 rounded text-sm"
            />
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={newBookcase.adjustable_shelves}
                onChange={e => setNewBookcase(p => ({ ...p, adjustable_shelves: e.target.checked }))}
                className="rounded"
              />
              Adjustable shelves
            </label>
            <input
              type="number"
              placeholder="Total height (mm)"
              value={newBookcase.total_height_mm}
              onChange={e => setNewBookcase(p => ({ ...p, total_height_mm: e.target.value }))}
              className="px-3 py-2 bg-slate-800 border border-slate-700 rounded text-sm"
            />
            <input
              type="number"
              placeholder="Total width (mm)"
              value={newBookcase.total_width_mm}
              onChange={e => setNewBookcase(p => ({ ...p, total_width_mm: e.target.value }))}
              className="px-3 py-2 bg-slate-800 border border-slate-700 rounded text-sm"
            />
          </div>
          <div className="flex gap-2 mt-3">
            <button
              onClick={() => addBookcaseMutation.mutate()}
              disabled={!newBookcase.name}
              className="px-4 py-2 bg-blue-600 rounded text-sm disabled:opacity-50"
            >
              Create
            </button>
            <button onClick={() => setShowAddBookcase(false)} className="px-4 py-2 bg-slate-700 rounded text-sm">Cancel</button>
          </div>
        </div>
      )}

      {/* Bookcase list */}
      {bookcases?.length === 0 && (
        <p className="text-center py-10 text-slate-500">No bookcases configured yet. Add one to get started.</p>
      )}

      <div className="space-y-3">
        {bookcases?.map((bc: Bookcase) => (
          <div key={bc.id} className="bg-slate-900 rounded-lg overflow-hidden">
            <button
              onClick={() => setExpandedBookcase(prev => prev === bc.id ? null : bc.id)}
              className="w-full flex items-center justify-between p-4 hover:bg-slate-800/50"
            >
              <div className="text-left">
                <p className="font-medium">{bc.name}</p>
                <p className="text-xs text-slate-500">
                  {bc.room && `${bc.room} - `}
                  {bc.total_width_mm && `${bc.total_width_mm}mm wide`}
                  {bc.adjustable_shelves ? ' - Adjustable' : ' - Fixed'}
                </p>
              </div>
              {expandedBookcase === bc.id ? <ChevronDown size={20} /> : <ChevronRight size={20} />}
            </button>

            {expandedBookcase === bc.id && bookcaseDetail && (
              <div className="border-t border-slate-800 p-4">
                {bookcaseDetail.shelves.length === 0 ? (
                  <p className="text-sm text-slate-500 mb-3">No shelves defined yet.</p>
                ) : (
                  <div className="space-y-2 mb-3">
                    {bookcaseDetail.shelves.map(shelf => (
                      <div key={shelf.id} className="flex items-center justify-between bg-slate-800 rounded p-3">
                        <div>
                          <span className="text-sm font-medium">Shelf #{shelf.shelf_number}</span>
                          {shelf.label && <span className="text-xs text-slate-500 ml-2">{shelf.label}</span>}
                        </div>
                        <div className="text-xs text-slate-500">
                          {shelf.usable_height_mm}mm H x {shelf.usable_width_mm}mm W
                          <span className="ml-2 text-slate-400">{shelf.books_count} books</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Add shelf form */}
                {showAddShelf === bc.id ? (
                  <div className="bg-slate-800 rounded p-3">
                    <div className="grid grid-cols-3 gap-2">
                      <input
                        type="number"
                        placeholder="Shelf #"
                        value={newShelf.shelf_number}
                        onChange={e => setNewShelf(p => ({ ...p, shelf_number: Number(e.target.value) }))}
                        className="px-2 py-1.5 bg-slate-700 border border-slate-600 rounded text-sm"
                      />
                      <input
                        type="number"
                        placeholder="Height (mm)"
                        value={newShelf.usable_height_mm}
                        onChange={e => setNewShelf(p => ({ ...p, usable_height_mm: e.target.value }))}
                        className="px-2 py-1.5 bg-slate-700 border border-slate-600 rounded text-sm"
                      />
                      <input
                        type="number"
                        placeholder="Width (mm)"
                        value={newShelf.usable_width_mm}
                        onChange={e => setNewShelf(p => ({ ...p, usable_width_mm: e.target.value }))}
                        className="px-2 py-1.5 bg-slate-700 border border-slate-600 rounded text-sm"
                      />
                    </div>
                    <div className="flex gap-2 mt-2">
                      <button
                        onClick={() => addShelfMutation.mutate(bc.id)}
                        className="px-3 py-1 bg-blue-600 rounded text-sm"
                      >
                        Add Shelf
                      </button>
                      <button onClick={() => setShowAddShelf(null)} className="px-3 py-1 bg-slate-700 rounded text-sm">Cancel</button>
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() => setShowAddShelf(bc.id)}
                    className="flex items-center gap-1 text-sm text-blue-400 hover:text-blue-300"
                  >
                    <Plus size={14} /> Add shelf
                  </button>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
