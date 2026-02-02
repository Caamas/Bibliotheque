/** API client for Bibliotheque backend. */

const API_BASE = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `API error: ${res.status}`);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

// --- Types ---

export interface Book {
  id: number;
  isbn_13?: string;
  isbn_10?: string;
  title: string;
  subtitle?: string;
  authors: string[];
  publisher?: string;
  publication_date?: string;
  page_count?: number;
  height_mm?: number;
  width_mm?: number;
  depth_mm?: number;
  cover_url?: string;
  cover_local?: string;
  genre?: string;
  language?: string;
  description?: string;
  babelio_url?: string;
  babelio_rating?: number;
  copies_count: number;
  created_at: string;
  updated_at: string;
}

export interface BookCopy {
  id: number;
  book_id: number;
  condition?: string;
  is_signed: boolean;
  signature_photo?: string;
  purchase_date?: string;
  purchase_location?: string;
  purchase_price?: number;
  personal_rating?: number;
  personal_review?: string;
  last_read_date?: string;
  read_count: number;
  storage_type: string;
  shelf_id?: number;
  shelf_position?: number;
  created_at: string;
  updated_at: string;
}

export interface BookDetail extends Book {
  copies: BookCopy[];
}

export interface BookList {
  items: Book[];
  total: number;
  page: number;
  page_size: number;
}

export interface ScanResult {
  found: boolean;
  already_owned: boolean;
  book?: Book;
  metadata?: Partial<Book>;
  message: string;
}

export interface Bookcase {
  id: number;
  name: string;
  room?: string;
  location_detail?: string;
  total_height_mm?: number;
  total_width_mm?: number;
  total_depth_mm?: number;
  adjustable_shelves: boolean;
  photo?: string;
  created_at: string;
}

export interface Shelf {
  id: number;
  bookcase_id: number;
  shelf_number: number;
  label?: string;
  usable_height_mm: number;
  usable_width_mm: number;
  usable_depth_mm?: number;
  books_count: number;
  created_at: string;
}

export interface BookcaseDetail extends Bookcase {
  shelves: Shelf[];
}

export interface Lending {
  id: number;
  book_copy_id: number;
  borrower_name: string;
  borrower_contact?: string;
  lent_date: string;
  expected_return_date?: string;
  actual_return_date?: string;
  is_active: boolean;
  is_overdue: boolean;
}

export interface Wishlist {
  id: number;
  name: string;
  share_token: string;
  items_count: number;
  created_at: string;
}

export interface WishlistItem {
  id: number;
  wishlist_id: number;
  book_id?: number;
  isbn?: string;
  title?: string;
  author?: string;
  priority: number;
  notes?: string;
  added_at: string;
}

export interface WishlistDetail extends Wishlist {
  items: WishlistItem[];
}

export interface OptimizeResult {
  assignments: { copy_id: number; shelf_id: number; position: number; book_title: string }[];
  unassigned_count: number;
  clusters: { name: string; min_height: number; max_height: number; books_count: number; required_shelf_height: number }[];
  shelf_utilization: { shelf_id: number; books_count: number; width_utilization_pct: number; height_wasted_mm: number }[];
  total_books: number;
  assigned_count: number;
  warnings: string[];
}

// --- API functions ---

export const api = {
  // Books
  listBooks: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return request<BookList>(`/books${qs}`);
  },
  getBook: (id: number) => request<BookDetail>(`/books/${id}`),
  createBook: (data: Partial<Book>) => request<Book>('/books', { method: 'POST', body: JSON.stringify(data) }),
  updateBook: (id: number, data: Partial<Book>) => request<Book>(`/books/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteBook: (id: number) => request<void>(`/books/${id}`, { method: 'DELETE' }),
  checkISBN: (isbn: string) => request<{ owned: boolean; book_id?: number; title?: string; personal_rating?: number; personal_review?: string }>(`/books/check/${isbn}`),

  // Copies
  createCopy: (data: { book_id: number; condition?: string }) => request<BookCopy>('/books/copies', { method: 'POST', body: JSON.stringify(data) }),
  updateCopy: (id: number, data: Partial<BookCopy>) => request<BookCopy>(`/books/copies/${id}`, { method: 'PUT', body: JSON.stringify(data) }),

  // Scanner
  scanISBN: (isbn: string) => request<ScanResult>('/scanner/scan', { method: 'POST', body: JSON.stringify({ isbn }) }),
  scanAndAdd: (isbn: string) => request<Book>('/scanner/scan-and-add', { method: 'POST', body: JSON.stringify({ isbn }) }),
  enrichBabelio: (bookId: number) => request<{ enriched: boolean; babelio_url?: string }>(`/scanner/enrich/${bookId}`, { method: 'POST' }),

  // Shelves
  listBookcases: () => request<Bookcase[]>('/shelves/bookcases'),
  getBookcase: (id: number) => request<BookcaseDetail>(`/shelves/bookcases/${id}`),
  createBookcase: (data: Partial<Bookcase>) => request<Bookcase>('/shelves/bookcases', { method: 'POST', body: JSON.stringify(data) }),
  createShelf: (data: Partial<Shelf> & { bookcase_id: number }) => request<Shelf>('/shelves', { method: 'POST', body: JSON.stringify(data) }),

  // Lendings
  listLendings: (activeOnly = true) => request<Lending[]>(`/lendings?active_only=${activeOnly}`),
  createLending: (data: { book_copy_id: number; borrower_name: string; borrower_contact?: string; expected_return_date?: string }) =>
    request<Lending>('/lendings', { method: 'POST', body: JSON.stringify(data) }),
  returnLending: (id: number) => request<Lending>(`/lendings/${id}/return`, { method: 'PUT', body: JSON.stringify({}) }),
  listOverdue: () => request<{ lending_id: number; borrower_name: string; days_overdue: number }[]>('/lendings/overdue'),

  // Wishlists
  listWishlists: () => request<Wishlist[]>('/wishlists'),
  getWishlist: (id: number) => request<WishlistDetail>(`/wishlists/${id}`),
  createWishlist: (name: string) => request<Wishlist>('/wishlists', { method: 'POST', body: JSON.stringify({ name }) }),
  addWishlistItem: (wishlistId: number, data: Partial<WishlistItem>) =>
    request<WishlistItem>(`/wishlists/${wishlistId}/items`, { method: 'POST', body: JSON.stringify(data) }),
  removeWishlistItem: (wishlistId: number, itemId: number) =>
    request<void>(`/wishlists/${wishlistId}/items/${itemId}`, { method: 'DELETE' }),
  getSharedWishlist: (token: string) => request<{ name: string; items: WishlistItem[] }>(`/wishlists/share/${token}`),

  // Optimizer
  optimize: (data?: { sort_order?: string; include_long_term_storage?: boolean }) =>
    request<OptimizeResult>('/optimizer/optimize', { method: 'POST', body: JSON.stringify(data || {}) }),
};
