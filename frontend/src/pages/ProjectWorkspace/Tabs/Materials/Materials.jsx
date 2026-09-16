import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { motion, AnimatePresence } from 'framer-motion';
import { uploadDocument, loadDocuments } from '../../../../features/project/spaceProjectSlice.js';
import { IconUpload, IconFile } from '../../../../components/icons/Icons.jsx';
import './Materials.css';

export default function Materials({ spaceId, projectId }) {
  const dispatch = useDispatch();
  const { documents } = useSelector((s) => s.spaceProject);
  const [drag, setDrag] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);

  useEffect(() => {
    if (spaceId && projectId) dispatch(loadDocuments({ spaceId, projectId }));
  }, [dispatch, spaceId, projectId]);

  const send = async (file) => {
    if (!file || uploading) return;
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

  return (
    <div className="materials">
      <motion.div
        className={drag ? 'dropzone drag' : 'dropzone'}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); send(e.dataTransfer.files[0]); }}
        onClick={() => document.getElementById('pdf-input').click()}
        whileHover={{ scale: 1.005 }}
        animate={drag ? { scale: 1.015 } : { scale: 1 }}
      >
        <div className="drop-icon"><IconUpload /></div>
        <strong>{uploading ? 'Uploading...' : 'Drag & drop your PDF here'}</strong>
        <span className="muted">or click to browse files</span>
        <input id="pdf-input" type="file" accept="application/pdf" hidden onChange={(e) => send(e.target.files[0])} />
      </motion.div>
      {uploading && <p className="muted"><span className="spinner" /> Uploading PDF...</p>}
      {uploadError && <p className="error">{uploadError}</p>}
      <p className="hint">Uploaded PDFs are processed asynchronously in the background. Text is extracted, chunked, and converted into vector embeddings for the AI Tutor.</p>
      <h4>Documents ({documents.length})</h4>
      <div className="doc-list">
        <AnimatePresence initial={false}>
          {documents.map((d) => (
            <motion.div
              key={d.id}
              className="doc-row"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              layout
            >
              <span className="doc-name"><IconFile size={19} /> {d.file_name}</span>
              <span className={`status ${d.status}`}>{d.status}</span>
            </motion.div>
          ))}
        </AnimatePresence>
        {documents.length === 0 && <p className="muted">No documents yet. Upload your first PDF above.</p>}
      </div>
    </div>
  );
}
