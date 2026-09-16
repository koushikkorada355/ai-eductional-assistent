import { useEffect, useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { uploadDocument, loadDocuments } from '../../../../features/project/spaceProjectSlice.js';
import './Materials.css';

export default function Materials({ spaceId, projectId }) {
  const dispatch = useDispatch();
  const { documents } = useSelector((s) => s.spaceProject);
  const [drag, setDrag] = useState(false);

  useEffect(() => {
    if (spaceId && projectId) dispatch(loadDocuments({ spaceId, projectId }));
  }, [dispatch, spaceId, projectId]);

  const send = (file) => {
    if (file) dispatch(uploadDocument({ spaceId, projectId, file }));
  };

  return (
    <div className="materials">
      <div
        className={drag ? 'dropzone drag' : 'dropzone'}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); send(e.dataTransfer.files[0]); }}
        onClick={() => document.getElementById('pdf-input').click()}
      >
        Drag & drop PDF here or click to upload
        <input id="pdf-input" type="file" accept="application/pdf" hidden onChange={(e) => send(e.target.files[0])} />
      </div>
      <p className="hint">Uploaded PDFs are processed asynchronously in the background. Text is extracted, chunked, and converted into vector embeddings for the AI Tutor.</p>
      <div className="doc-list">
        {documents.map((d) => (
          <div key={d.id} className="doc-row">
            <span>{d.file_name}</span>
            <span className={`status ${d.status}`}>{d.status}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
