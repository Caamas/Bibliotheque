import { Routes, Route, NavLink } from 'react-router-dom'
import { BookOpen, ScanBarcode, BookMarked, Handshake, LayoutGrid, Sparkles } from 'lucide-react'
import Library from './pages/Library'
import Scanner from './pages/Scanner'
import Shelves from './pages/Shelves'
import Lendings from './pages/Lendings'
import Wishlists from './pages/Wishlists'
import Optimizer from './pages/Optimizer'
import BookDetail from './pages/BookDetail'
import SharedWishlist from './pages/SharedWishlist'

const navItems = [
  { to: '/', icon: BookOpen, label: 'Library' },
  { to: '/scan', icon: ScanBarcode, label: 'Scan' },
  { to: '/shelves', icon: LayoutGrid, label: 'Shelves' },
  { to: '/lendings', icon: Handshake, label: 'Lent' },
  { to: '/wishlists', icon: BookMarked, label: 'Wishlist' },
  { to: '/optimizer', icon: Sparkles, label: 'Optimize' },
]

export default function App() {
  return (
    <div className="flex flex-col min-h-dvh">
      <main className="flex-1 pb-20 px-4 pt-4 max-w-6xl mx-auto w-full">
        <Routes>
          <Route path="/" element={<Library />} />
          <Route path="/scan" element={<Scanner />} />
          <Route path="/shelves" element={<Shelves />} />
          <Route path="/lendings" element={<Lendings />} />
          <Route path="/wishlists" element={<Wishlists />} />
          <Route path="/optimizer" element={<Optimizer />} />
          <Route path="/book/:id" element={<BookDetail />} />
          <Route path="/wishlist/share/:token" element={<SharedWishlist />} />
        </Routes>
      </main>

      <nav className="fixed bottom-0 left-0 right-0 bg-slate-900 border-t border-slate-800 safe-bottom">
        <div className="flex justify-around items-center max-w-lg mx-auto">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex flex-col items-center py-2 px-3 text-xs transition-colors ${
                  isActive ? 'text-blue-400' : 'text-slate-500 hover:text-slate-300'
                }`
              }
            >
              <Icon size={20} />
              <span className="mt-1">{label}</span>
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  )
}
