import { useMemo, useState } from 'react'
import { AlertTriangle, ArrowRight, FileSearch, Files, FolderOpen, SearchX } from 'lucide-react'
import { DocumentDetailPanel } from '../components/documents/DocumentDetailPanel'
import { DocumentTable } from '../components/documents/DocumentTable'
import { FixtureTag } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { EmptyState, PageHeader } from '../components/ui/Layout'
import { SearchInput, Segmented, ToggleChip } from '../components/ui/Toolbar'
import { useApp } from '../state/AppState'
import type { Category } from '../types/api'

type Filter = 'all' | Category | 'skipped'

export function FilesPage() {
  const { state, rows, selectDoc, navigate, chooseSampleFolder, counts, usingFixtures } = useApp()
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<Filter>('all')
  const [reviewOnly, setReviewOnly] = useState(false)

  const countBy = (c: Category) => rows.filter((r) => r.category === c).length
  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    return rows.filter((r) => {
      if (filter === 'skipped' && r.status !== 'skipped') return false
      if (filter !== 'all' && filter !== 'skipped' && r.category !== filter) return false
      if (reviewOnly && r.status !== 'needs_review' && r.status !== 'failed') return false
      if (!q) return true
      return [r.filename, r.relPath, r.merchant ?? ''].some((s) => s.toLowerCase().includes(q))
    })
  }, [rows, query, filter, reviewOnly])
  const selectedRow = rows.find((r) => r.id === state.selectedDocId) ?? null

  if (!state.scan) {
    return (
      <div className="flex flex-1 flex-col">
        <PageHeader title="Files" description="Classified documents and their extracted fields appear here after a scan." />
        <EmptyState
          icon={Files}
          title={state.phase === 'scanning' ? 'Scan in progress' : 'No documents yet'}
          className="flex-1"
          actions={
            state.phase === 'scanning' ? (
              <Button onClick={() => navigate('scanning')}>View progress</Button>
            ) : (
              <>
                {usingFixtures && (
                  <Button icon={FileSearch} onClick={chooseSampleFolder}>
                    Use sample folder
                  </Button>
                )}
                <Button variant="primary" icon={FolderOpen} onClick={() => navigate('folder')}>
                  Select Folder
                </Button>
              </>
            )
          }
        >
          Select a folder and run a scan to see classified documents.
        </EmptyState>
      </div>
    )
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <PageHeader
        title="Files"
        meta={usingFixtures && <FixtureTag />}
        breadcrumbs={[state.folder?.name ?? 'Folder', 'Files']}
        description="Proposed classifications and extracted fields. Click a row to inspect evidence and correct values."
        actions={
          <Button variant="primary" iconRight={ArrowRight} onClick={() => navigate('plan')}>
            Review organization plan
          </Button>
        }
      />
      <div className="flex min-h-0 flex-1">
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex shrink-0 flex-wrap items-center gap-2 px-6 py-3">
            <SearchInput value={query} onChange={setQuery} placeholder="Search files or merchants" />
            <Segmented<Filter>
              label="Category filter"
              value={filter}
              onChange={setFilter}
              options={[
                { value: 'all', label: 'All', count: rows.length },
                { value: 'invoice', label: 'Invoices', count: countBy('invoice') },
                { value: 'receipt', label: 'Receipts', count: countBy('receipt') },
                { value: 'other', label: 'Other', count: countBy('other') },
                { value: 'uncertain', label: 'Uncertain', count: countBy('uncertain') },
                { value: 'skipped', label: 'Skipped', count: counts.skipped },
              ]}
            />
            <ToggleChip active={reviewOnly} onClick={() => setReviewOnly((v) => !v)}>
              <AlertTriangle size={13} aria-hidden />
              Needs review
              <span className="tabular">{counts.needsReview}</span>
            </ToggleChip>
          </div>
          <div className="scroll-area mx-6 mb-6 min-h-0 flex-1 rounded-lg border border-line bg-surface-1">
            {visible.length === 0 ? (
              <EmptyState
                icon={reviewOnly && counts.needsReview === 0 ? FileSearch : SearchX}
                title={reviewOnly && counts.needsReview === 0 ? 'Nothing needs review' : 'No matching files'}
                actions={
                  <Button
                    size="sm"
                    onClick={() => {
                      setQuery('')
                      setFilter('all')
                      setReviewOnly(false)
                    }}
                  >
                    Clear filters
                  </Button>
                }
              >
                {reviewOnly && counts.needsReview === 0 ? 'Every flagged record has been reviewed.' : 'Try a different search or category.'}
              </EmptyState>
            ) : (
              <DocumentTable rows={visible} selectedId={state.selectedDocId} onSelect={(id) => selectDoc(id === state.selectedDocId ? null : id)} compact={selectedRow !== null} />
            )}
          </div>
        </div>
        {selectedRow && <DocumentDetailPanel key={selectedRow.id} row={selectedRow} onClose={() => selectDoc(null)} />}
      </div>
    </div>
  )
}
