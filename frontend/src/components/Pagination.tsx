import React from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

interface PaginationProps {
  total: number
  page: number
  pageSize?: number
  onPage: (page: number) => void
}

const Pagination: React.FC<PaginationProps> = ({ total, page, pageSize = 100, onPage }) => {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const currentPage = Math.min(page, totalPages)
  if (totalPages <= 1) return null

  return (
    <div className="flex items-center justify-between gap-2 mt-4 pt-4 border-t border-slate-700 text-sm text-slate-400">
      <span>
        {total} registros · Página {currentPage} de {totalPages}
      </span>
      <div className="flex items-center gap-1">
        <button
          type="button"
          disabled={currentPage <= 1}
          onClick={() => onPage(currentPage - 1)}
          className="p-2 rounded-lg text-slate-300 hover:bg-slate-800 hover:text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          title="Anterior"
        >
          <ChevronLeft size={16} />
        </button>
        <button
          type="button"
          disabled={currentPage >= totalPages}
          onClick={() => onPage(currentPage + 1)}
          className="p-2 rounded-lg text-slate-300 hover:bg-slate-800 hover:text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          title="Siguiente"
        >
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  )
}

export default Pagination