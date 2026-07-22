import React, { useState } from 'react';
import { Upload, FileText } from 'lucide-react';
import './UploadBox.css';

function UploadBox({ selectedFile, previewUrl, onFileChange, onDrop }) {
  const [dragging, setDragging] = useState(false);
  const isImage = selectedFile?.type?.startsWith('image/');
  return <div className="upload-box">
    {!selectedFile ? <div className={`upload-dropzone ${dragging ? 'dragging' : ''}`} onDrop={(e) => { setDragging(false); onDrop(e); }} onDragOver={(e) => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)}>
      <input type="file" id="fileUpload" className="file-input" accept="image/jpeg,application/pdf,.jpg,.jpeg,.pdf" onChange={onFileChange} />
      <label htmlFor="fileUpload" className="upload-label">
        <div className="upload-icon-wrap"><Upload size={24} /></div>
        <p className="upload-title">Drop Your Files Here or <span>Browse</span></p>
        <p className="upload-hint">JPG or PDF</p>
      </label>
    </div> : <div className="file-preview">
      <div className="preview-wrap">{isImage && previewUrl ? <img src={previewUrl} alt="Preview" className="preview-img" /> : <div className="preview-placeholder"><FileText size={36} /><span>PDF Document</span></div>}</div>
      <div className="file-info"><FileText size={16} className="file-info-icon" /><span className="file-info-name">{selectedFile.name}</span></div>
    </div>}
  </div>;
}
export default UploadBox;
