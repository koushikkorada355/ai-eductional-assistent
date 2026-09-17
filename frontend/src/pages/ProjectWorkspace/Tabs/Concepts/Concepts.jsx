import React, { useEffect, useMemo, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { motion } from 'framer-motion';
import { loadConcepts } from '../../../../features/concepts/conceptsSlice.js';
import { loadDocuments } from '../../../../features/project/spaceProjectSlice.js';
import { loadProjectAnalytics } from '../../../../features/analytics/analyticsSlice.js';
import { PageHeader, Stat, StatusBadge, EmptyState } from '../../../../components/ui/ui.jsx';
import { IconArrowLeft, IconFolder, IconX } from '../../../../components/icons/Icons.jsx';

function levelOf(score) {
  if (score >= 70) return { label: 'Strong', status: 'strong' };
  if (score >= 40) return { label: 'Learning', status: 'learning' };
  return { label: 'Needs work', status: 'weak' };
}

function masteryOf(c) {
  const raw = c?.mastery_level ?? c?.mastery ?? 0;
  const n = Number(raw);
  if (!Number.isFinite(n)) return 0;
  return Math.min(100, Math.max(0, Math.round(n)));
}

const fillColor = (score) => (score >= 70 ? 'bg-accent' : score >= 40 ? 'bg-primary' : 'bg-danger');
const PREVIEW_COUNT = 8;

function ConceptCard({ concept, onOpen }) {
  const score = masteryOf(concept);
  const level = levelOf(score);
  return (
    <motion.div
      role="button"
      tabIndex={0}
      aria-label={`Open concept ${concept.name}, mastery ${score} percent`}
      onClick={() => onOpen(concept.id)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onOpen(concept.id);
        }
      }}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex cursor-pointer flex-col gap-2 rounded-md border border-line bg-surface p-4 shadow-sm hover:border-primary hover:shadow-md focus-visible:outline-2 focus-visible:outline-primary"
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-display text-sm font-semibold text-ink">{concept.name}</h3>
        <StatusBadge status={level.status}>{level.label}</StatusBadge>
      </div>
      {concept.description && <p className="line-clamp-2 text-[13px] text-muted">{concept.description}</p>}
      <div className="flex items-center justify-between text-xs font-medium text-muted">
        <span>Mastery</span>
        <span>{score}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-canvas">
        <div className={`h-full rounded-full ${fillColor(score)}`} style={{ width: `${score}%` }} />
      </div>
    </motion.div>
  );
}

export default function Concepts({ spaceId, projectId }) {
  const dispatch = useDispatch();
  const { concepts, status, error } = useSelector((s) => s.concepts);
  const { documents } = useSelector((s) => s.spaceProject);
  const { project: analytics } = useSelector((s) => s.analytics);
  const [selectedId, setSelectedId] = useState(null);
  const [query, setQuery] = useState('');
  const [expandedDocs, setExpandedDocs] = useState([]);

  useEffect(() => {
    if (spaceId && projectId) {
      dispatch(loadConcepts({ spaceId, projectId }));
      dispatch(loadDocuments({ spaceId, projectId }));
      dispatch(loadProjectAnalytics({ spaceId, projectId }));
    }
  }, [dispatch, spaceId, projectId]);

  const docById = useMemo(() => {
    const map = {};
    (documents || []).forEach((d) => { map[d.id] = d; });
    return map;
  }, [documents]);

  // Group by source document (document order first), then honestly-labeled
  // fallback for concepts whose source was never recorded.
  const groups = useMemo(() => {
    const list = concepts || [];
    const byDoc = {};
    const unattributed = [];
    list.forEach((c) => {
      if (c.document_id && docById[c.document_id]) {
        (byDoc[c.document_id] = byDoc[c.document_id] || []).push(c);
      } else {
        unattributed.push(c);
      }
    });
    const docGroups = (documents || [])
      .filter((d) => (byDoc[d.id] || []).length > 0)
      .map((d) => ({ key: d.id, doc: d, items: [...byDoc[d.id]].sort((a, b) => masteryOf(a) - masteryOf(b)) }));
    // Documents deleted after extraction: keep their concepts visible rather
    // than dropping them, under the fallback group.
    Object.entries(byDoc).forEach(([docId, items]) => {
      if (!docById[docId]) unattributed.push(...items);
    });
    if (unattributed.length > 0) {
      docGroups.push({
        key: '__unknown__',
        doc: null,
        items: [...unattributed].sort((a, b) => masteryOf(a) - masteryOf(b)),
      });
    }
    return docGroups;
  }, [concepts, documents, docById]);

  const q = query.trim().toLowerCase();
  const visibleGroups = useMemo(() => {
    if (!q) return groups;
    return groups
      .map((g) => ({
        ...g,
        items: g.items.filter((c) =>
          c.name.toLowerCase().includes(q) || (c.description || '').toLowerCase().includes(q)
        ),
      }))
      .filter((g) => g.items.length > 0);
  }, [groups, q]);

  const allConcepts = useMemo(() => concepts || [], [concepts]);
  const avg = useMemo(() => {
    if (allConcepts.length === 0) return 0;
    return allConcepts.reduce((s, c) => s + masteryOf(c), 0) / allConcepts.length;
  }, [allConcepts]);
  const weakest = useMemo(
    () => [...allConcepts].sort((a, b) => masteryOf(a) - masteryOf(b))[0],
    [allConcepts]
  );

  const toggleDoc = (key) => {
    setExpandedDocs((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]));
  };

  const selected = selectedId ? allConcepts.find((c) => c.id === selectedId) : null;

  /* ---------------- detail: definition + mastery + source ---------------- */
  if (selected) {
    const score = masteryOf(selected);
    const level = levelOf(score);
    const history = (analytics?.conceptHistory?.[selected.id]) || [];
    const mistakes = history.filter((h) => !h.is_correct);
    const sourceDoc = selected.document_id ? docById[selected.document_id] || null : null;
    return (
      <div className="flex flex-col gap-4">
        <button
          type="button"
          onClick={() => setSelectedId(null)}
          className="inline-flex items-center gap-1.5 self-start rounded-md px-2 py-1 text-[13px] font-medium text-muted hover:bg-primary-soft hover:text-primary [&>svg]:h-3.5 [&>svg]:w-3.5"
        >
          <IconArrowLeft size={14} /> Back to Concepts
        </button>
        <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-3">
          <div className="flex flex-col gap-4 lg:col-span-2">
            <div className="flex flex-col gap-2 rounded-card border border-line bg-surface p-5 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <h3 className="font-display text-base font-bold text-ink">{selected.name}</h3>
                <StatusBadge status={level.status}>{level.label}</StatusBadge>
              </div>
              {selected.description
                ? <p className="text-[13px] text-muted">{selected.description}</p>
                : <p className="text-[13px] italic text-muted">No definition recorded for this concept.</p>}
              <div className="flex items-center justify-between text-xs font-medium text-muted">
                <span>Mastery</span><span>{score}%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-canvas">
                <div className={`h-full rounded-full ${fillColor(score)}`} style={{ width: `${score}%` }} />
              </div>
            </div>
            <div className="flex flex-col gap-2 rounded-card border border-line bg-surface p-5 shadow-sm">
              <h3 className="font-display text-sm font-semibold text-heading">Recent Mistakes</h3>
              {mistakes.length === 0 && (
                <p className="text-[13px] text-accent">No recent mistakes — keep it up.</p>
              )}
              {mistakes.map((m, i) => (
                <div key={i} className="rounded-md bg-canvas px-3.5 py-3">
                  <p className="text-sm text-ink">{m.feedback || 'Answered incorrectly.'}</p>
                  <span className="text-[11px] text-muted">{m.created_at ? new Date(m.created_at).toLocaleDateString() : ''}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-2 rounded-card border border-line bg-surface p-5 shadow-sm">
              <h3 className="font-display text-sm font-semibold text-heading">Source Document</h3>
              {sourceDoc ? (
                <div className="flex items-center gap-2.5">
                  <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary-soft text-primary [&>svg]:h-[18px] [&>svg]:w-[18px]">
                    <IconFolder />
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-[13px] font-semibold text-ink" title={sourceDoc.file_name}>
                      {sourceDoc.file_name}
                    </span>
                    <span className="block text-[11px] text-muted">
                      {sourceDoc.pages != null ? `${sourceDoc.pages} pages` : 'Source reference'}
                    </span>
                  </span>
                </div>
              ) : (
                <p className="text-[13px] text-muted">Not recorded — this concept was extracted before source tracking.</p>
              )}
            </div>
            <div className="flex flex-col gap-1 rounded-card border border-line border-l-2 border-l-primary bg-surface p-5 shadow-sm">
              <h3 className="font-display text-sm font-semibold text-heading">Suggested Practice</h3>
              <p className="text-[11px] text-muted">
                {score < 40
                  ? `Mastery is ${score}%. Generate a quiz targeting '${selected.name}' to improve fastest.`
                  : `Mastery is ${score}%. An assignment on '${selected.name}' will lock it in.`}
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  /* ---------------- workspace: grouped by source document ---------------- */
  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Concepts"
        title="Source Documents & Concepts"
        sub="Knowledge extracted from your project documents, grouped by the source each concept came from."
        actions={(
          <button
            type="button"
            onClick={() => dispatch(loadConcepts({ spaceId, projectId }))}
            disabled={status === 'loading'}
            className="inline-flex min-h-9 items-center justify-center gap-2 whitespace-nowrap rounded-md border border-line bg-surface px-4 text-sm font-medium text-ink hover:bg-canvas disabled:opacity-50"
          >
            {status === 'loading' ? 'Refreshing...' : 'Refresh'}
          </button>
        )}
      />

      {error && <div className="error-banner">{error}</div>}

      {allConcepts.length > 0 && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-3">
          <Stat value={allConcepts.length} label="Extracted concepts" />
          <Stat value={`${Math.round(avg)}%`} label="Avg mastery" />
          <Stat value={weakest ? weakest.name : '—'} label="Weakest concept" />
        </div>
      )}

      {status === 'loading' && allConcepts.length === 0 && (
        <p className="text-sm text-muted">Loading concepts...</p>
      )}

      {status !== 'loading' && allConcepts.length === 0 && !error && (
        <EmptyState
          title="No concepts yet"
          body="Upload a PDF in Materials to extract concepts for this project."
        />
      )}

      {allConcepts.length > 0 && (
        <div className="flex max-w-xl items-center gap-2 rounded-md border border-line bg-surface px-3 shadow-sm focus-within:border-primary">
          <label htmlFor="concept-search" className="sr-only">Search concepts</label>
          <input
            id="concept-search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search concepts across all source documents..."
            autoComplete="off"
            className="min-h-10 min-w-0 flex-1 border-0 bg-transparent text-sm focus:outline-none"
          />
          {query && (
            <button
              type="button"
              onClick={() => setQuery('')}
              aria-label="Clear search"
              className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-muted hover:bg-canvas hover:text-ink [&>svg]:h-3.5 [&>svg]:w-3.5"
            >
              <IconX size={14} />
            </button>
          )}
        </div>
      )}

      {allConcepts.length > 0 && visibleGroups.length === 0 && (
        <EmptyState
          title="No matching concepts"
          body={`Nothing matches "${query.trim()}". Try a different search.`}
          actions={(
            <button
              type="button"
              onClick={() => setQuery('')}
              className="inline-flex min-h-9 items-center justify-center rounded-md border border-line bg-surface px-4 text-sm font-medium text-ink hover:bg-canvas"
            >
              Clear search
            </button>
          )}
        />
      )}

      {visibleGroups.map((g) => {
        const expanded = expandedDocs.includes(g.key);
        const shown = expanded ? g.items : g.items.slice(0, PREVIEW_COUNT);
        const groupAvg = Math.round(g.items.reduce((s, c) => s + masteryOf(c), 0) / g.items.length);
        return (
          <section key={g.key} aria-label={g.doc ? `Concepts from ${g.doc.file_name}` : 'Concepts without recorded source'}>
            <div className="flex flex-wrap items-center gap-3">
              <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary-soft text-primary [&>svg]:h-5 [&>svg]:w-5">
                <IconFolder />
              </span>
              <div className="min-w-0 flex-1">
                <h3 className="truncate font-display text-[15px] font-bold text-heading" title={g.doc ? g.doc.file_name : undefined}>
                  {g.doc ? g.doc.file_name : 'Other Concepts'}
                </h3>
                <p className="text-xs text-muted">
                  {g.doc
                    ? `${g.items.length} extracted concept${g.items.length === 1 ? '' : 's'} · ${groupAvg}% avg mastery`
                    : `${g.items.length} concept${g.items.length === 1 ? '' : 's'} · source not recorded (extracted before source tracking)`}
                </p>
              </div>
            </div>
            <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
              {shown.map((c) => (
                <ConceptCard key={c.id} concept={c} onOpen={setSelectedId} />
              ))}
            </div>
            {g.items.length > PREVIEW_COUNT && (
              <button
                type="button"
                onClick={() => toggleDoc(g.key)}
                aria-expanded={expanded}
                className="mt-3 inline-flex min-h-9 items-center justify-center rounded-md border border-line bg-surface px-4 text-sm font-medium text-ink hover:border-primary hover:text-primary"
              >
                {expanded ? 'Show less' : `View all ${g.items.length} concepts →`}
              </button>
            )}
          </section>
        );
      })}
    </div>
  );
}
