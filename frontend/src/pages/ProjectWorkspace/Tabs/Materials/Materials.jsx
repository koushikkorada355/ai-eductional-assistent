import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { motion, AnimatePresence } from 'framer-motion';
import { uploadDocument, loadDocuments, retryDocument, removeDocument } from '../../../../features/project/spaceProjectSlice.js';
import { fetchEvidence } from '../../../../features/project/projectApi.js';
import ConfirmModal from '../../../../components/ConfirmModal/ConfirmModal.jsx';
import { PageHeader, StatusBadge } from '../../../../components/ui/ui.jsx';
import { IconUpload, IconFile, IconArrowLeft, IconX } from '../../../../components/icons/Icons.jsx';

export default function Materials({ spaceId, projectId }) {
  const dispatch = useDispatch();
  const { documents } = useSelector((s) => s.spaceProject);
  const [drag, setDrag] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [evidence, setEvidence] = useState(null);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(null);

  useEffect(() => {
    if (spaceId && projectId) dispatch(loadDocuments({ spaceId, projectId }));
  }, [dispatch, spaceId, projectId]);

  const MAX_MB = 25;
  const send = async (file) => {
    if (!file || uploading) return;
    // Fail fast in the browser with an actionable message (saves a round-trip).
    if (file.size === 0) {
      setUploadError('That file is empty. Please choose a valid PDF.');
      return;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      setUploadError(`PDF too large (${(file.size / (1024 * 1024)).toFixed(1)}MB). Max is ${MAX_MB}MB.`);
      return;
    }
    const isPdf = file.type === 'application/pdf' || (file.name || '').toLowerCase().endsWith('.pdf');
    if (!isPdf) {
      setUploadError('Only PDF files are allowed.');
      return;
    }
    setUploading(true);
    setUploadError(null);
    try {
      await dispatch(uploadDocument({ spaceId, projectId, file })).unwrap();
    } catch (e) {
      setUploadError(typeof e === 'string' ? e : 'PDF upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  const openDetail = async (d) => {
    setSelectedId(d.id);
    setEvidence(null);
    setEvidenceLoading(true);
    try {
      const data = await fetchEvidence(spaceId, projectId, d.id);
      setEvidence(data);
    } catch (e) {
      setEvidence({ error: 'Could not load extracted evidence.' });
    } finally {
      setEvidenceLoading(false);
    }
  };

  const selected = documents.find((d) => d.id === selectedId);

  if (selected) {
    return (
      <div className="flex max-w-3xl flex-col gap-4">
        <button
          type="button"
          onClick={() => { setSelectedId(null); setEvidence(null); }}
          className="inline-flex items-center gap-1.5 self-start rounded-md px-2 py-1 text-[13px] font-medium text-muted hover:bg-primary-soft hover:text-primary [&>svg]:h-3.5 [&>svg]:w-3.5"
        >
          <IconArrowLeft size={14} /> Back to documents
        </button>
        <div className="flex flex-col gap-3 rounded-card border border-line bg-surface p-5 shadow-sm">
          <span className="flex items-center gap-2 text-sm font-semibold text-ink [&>svg]:h-[19px] [&>svg]:w-[19px]">
            <IconFile size={19} /> <span className="truncate">{selected.file_name}</span>
          </span>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={selected.status} />
            <span className="text-[11px] text-muted">{selected.pages || 0} pages · {selected.chunks || 0} chunks</span>
          </div>
          {selected.error && (
            <p className={selected.status === 'failed' ? 'error' : 'text-sm text-muted'}>{selected.error}</p>
          )}
          <h4 className="font-display text-sm font-semibold text-heading">Extracted Evidence</h4>
          {evidenceLoading && <p className="text-sm text-muted">Loading evidence...</p>}
          {evidence?.error && <p className="error">{evidence.error}</p>}
          {(evidence?.evidence || []).map((ev, i) => (
            <div key={i} className="flex flex-col gap-1 rounded-md bg-canvas px-3.5 py-3">
              <span className="text-[11px] font-semibold text-primary">Page {ev.page_number}</span>
              <p className="text-sm text-muted">{ev.excerpt}</p>
            </div>
          ))}
          {evidence && !(evidence.evidence || []).length && !evidence.error && !evidenceLoading && (
            <p className="text-sm text-muted">No evidence extracted yet{selected.status !== 'ready' ? ' — processing is still running' : ''}.</p>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        eyebrow="Materials"
        title="Documents"
        sub="Upload PDFs — they are processed in the background into chunks and embeddings for the AI Tutor."
      />
      <motion.div
        role="button"
        tabIndex={0}
        aria-label="Upload a PDF: drag and drop a file here or press Enter to browse"
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); send(e.dataTransfer.files[0]); }}
        onClick={() => document.getElementById('pdf-input').click()}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            document.getElementById('pdf-input').click();
          }
        }}
        whileHover={{ scale: 1.005 }}
        animate={drag ? { scale: 1.015 } : { scale: 1 }}
        className={`flex cursor-pointer flex-col items-center gap-1.5 rounded-card border-2 border-dashed px-6 py-10 text-center shadow-sm focus-visible:outline-2 focus-visible:outline-primary ${
          drag ? 'border-primary bg-primary-soft' : 'border-line bg-surface'
        }`}
      >
        <div className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-primary-soft text-primary [&>svg]:h-10 [&>svg]:w-10">
          <IconUpload />
        </div>
        <strong className="text-sm text-ink">{uploading ? 'Uploading...' : 'Drag & drop your PDF here'}</strong>
        <span className="text-[13px] text-muted">or click to browse files</span>
        <input id="pdf-input" type="file" accept="application/pdf" hidden onChange={(e) => send(e.target.files[0])} />
      </motion.div>
      {uploading && <p className="flex items-center gap-3 text-sm text-muted"><span className="spinner" /> Uploading PDF...</p>}
      {uploadError && <p className="error">{uploadError}</p>}
      <div className="flex items-center justify-between">
        <h4 className="font-display text-sm font-semibold text-heading">Documents ({documents.length})</h4>
      </div>
      <div className="overflow-hidden rounded-card border border-line bg-surface shadow-sm">
        <AnimatePresence initial={false}>
          {documents.map((d) => (
            <motion.div
              key={d.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              layout
              className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-line px-4 py-3 last:border-b-0 sm:px-5"
            >
              <span className="flex min-w-0 flex-1 items-center gap-2 text-sm font-medium text-ink [&>svg]:h-[19px] [&>svg]:w-[19px] [&>svg]:shrink-0">
                <IconFile size={19} /> <span className="truncate">{d.file_name}</span>
              </span>
              <span className="hidden text-[11px] text-muted md:inline">{d.pages != null ? `${d.pages} pages · ` : ''}{d.created_at ? new Date(d.created_at).toLocaleDateString() : ''}</span>
              <StatusBadge status={d.status} />
              {d.status === 'failed' && d.error && (
                <span className="w-full text-[12px] text-danger" title={d.error}>{d.error}</span>
              )}
              {d.status === 'queued' && d.error && (
                <span className="w-full text-[12px] text-muted" title={d.error}>{d.error}</span>
              )}
              <span className="flex items-center gap-1">
                <button type="button" onClick={() => openDetail(d)} className="rounded-md px-2 py-1 text-[13px] font-medium text-muted hover:bg-primary-soft hover:text-primary">View</button>
                {(d.status === 'failed' || d.status === 'queued') && (
                  <button
                    type="button"
                    onClick={() => dispatch(retryDocument({ spaceId, projectId, documentId: d.id }))}
                    className="inline-flex min-h-9 items-center justify-center gap-2 whitespace-nowrap rounded-md border border-line bg-surface px-4 text-sm font-medium text-ink hover:bg-canvas"
                  >
                    Retry
                  </button>
                )}
                <button
                  type="button"
                  title="Delete document"
                  aria-label={`Delete document ${d.file_name}`}
                  onClick={() => setConfirmDelete({
                    title: 'Delete document?',
                    message: `"${d.file_name}" and its extracted data will be permanently removed.`,
                    onConfirm: () => { dispatch(removeDocument({ spaceId, projectId, documentId: d.id })); setConfirmDelete(null); },
                  })}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted hover:bg-danger-soft hover:text-danger [&>svg]:h-3.5 [&>svg]:w-3.5"
                ><IconX size={14} /></button>
              </span>
            </motion.div>
          ))}
        </AnimatePresence>
        {documents.length === 0 && <p className="px-5 py-4 text-[13px] text-muted">No documents yet. Upload your first PDF above.</p>}
      </div>
      <ConfirmModal
        open={!!confirmDelete}
        title={confirmDelete?.title}
        message={confirmDelete?.message}
        onConfirm={confirmDelete?.onConfirm}
        onCancel={() => setConfirmDelete(null)}
      />
    </div>
  );
}
