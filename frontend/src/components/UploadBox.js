import React, { useState } from 'react';
import { Upload, FileText } from 'lucide-react';
import './UploadBox.css';

function UploadBox({ selectedFile, previewUrl, onFileChange, onDrop }) {
  const [dragging, setDragging] = useState(false);

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragging(true);
  };

  const handleDragLeave = () => setDragging(false);

  const handleDrop = (e) => {
    setDragging(false);
    onDrop(e);
  };

  // M11: Determine if uploaded file is an image for preview rendering
  const isImage = selectedFile && selectedFile.type?.startsWith('image/');

  const formatSize = (bytes) => {
    if (bytes >= 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    return (bytes / 1024).toFixed(1) + ' KB';
  };

  return (
    <div className="upload-box">
      {!selectedFile ? (
        <div
          className={`upload-dropzone ${dragging ? 'dragging' : ''}`}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
        >
          <input
            type="file"
            id="fileUpload"
            className="file-input"
            accept="image/jpeg,image/png,image/webp,application/pdf"
            onChange={onFileChange}
          />
          <label htmlFor="fileUpload" className="upload-label">
            <div className="upload-icon-wrap">
              <Upload size={24} />
            </div>
            <p className="upload-title">Drop your file here, or <span>browse</span></p>
            <p className="upload-hint">JPG, PNG, WebP, or PDF — up to 10 MB</p>
            <div className="upload-reqs">
              <p className="upload-reqs-heading">Requirements</p>
              <p className="upload-hint">Max 10 MB file size</p>
              <p className="upload-hint">Questions labeled Q1, Q2…</p>
              <p className="upload-hint">Student name &amp; ID visible</p>
            </div>
          </label>
        </div>
      ) : (
        <div className="file-preview">
          <div className="preview-wrap">
            {isImage && previewUrl ? (
              <img src={previewUrl} alt="Preview" className="preview-img" />
            ) : (
              <div className="preview-placeholder">
                <FileText size={36} />
                <span>PDF Document</span>
              </div>
            )}
          </div>
          <div className="file-info">
            <FileText size={16} className="file-info-icon" />
            <span className="file-info-name">{selectedFile.name}</span>
            <span className="file-info-size">{formatSize(selectedFile.size)}</span>
          </div>
        </div>
      )}
    </div>
  );
}

export default UploadBox;
