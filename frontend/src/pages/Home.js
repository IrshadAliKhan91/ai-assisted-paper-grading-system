import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader, Zap } from 'lucide-react';
import './Home.css';
import UploadBox from '../components/UploadBox';
import { api } from '../services/api';

function Home({ onResultReady }) {
  const navigate = useNavigate();
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const isSupportedUploadFile = (file) => {
    const name = file?.name?.toLowerCase() || '';
    const type = file?.type || '';
    return (
      type.startsWith('image/')
      || type === 'application/pdf'
      || /\.(jpe?g|png|webp|pdf)$/i.test(name)
    );
  };

  const isPdfFile = (file) => {
    const name = file?.name?.toLowerCase() || '';
    return file?.type === 'application/pdf' || name.endsWith('.pdf');
  };

  // M7: Clean up object URLs on change
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (file.size > 10 * 1024 * 1024) {
        setError('File size must be less than 10MB');
        return;
      }
      if (!isSupportedUploadFile(file)) {
        setError('Please upload a JPG, PNG, WebP, or PDF file.');
        return;
      }
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      setSelectedFile(file);
      
      if (isPdfFile(file)) {
        setPreviewUrl(null);
      } else {
        setPreviewUrl(URL.createObjectURL(file));
      }
      setError('');
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) {
      if (file.size > 10 * 1024 * 1024) {
        setError('File size must be less than 10MB');
        return;
      }
      if (isSupportedUploadFile(file)) {
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        setSelectedFile(file);
        
        if (isPdfFile(file)) {
            setPreviewUrl(null); // Or set a placeholder image
        } else {
            setPreviewUrl(URL.createObjectURL(file));
        }
        setError('');
      } else {
        setError('Please upload a JPG, PNG, WebP, or PDF file.');
      }
    }
  };

  const uploadAndGrade = async () => {
    if (!selectedFile) return;
    setLoading(true);
    setError('');
    try {
      const result = await api.gradePaper(selectedFile);
      onResultReady(result);
    } catch (err) {
      setError(err.message || 'Failed to process paper. Please check backend connection.');
    } finally {
      setLoading(false);
    }
  };

  const resetUpload = () => {
    setSelectedFile(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setError('');
  };

  return (
    <div className="home-page">

      {/* ---- Hero ---- */}
      <section className="hero">
        <div className="hero-badge">
          <Zap size={14} />
          AI-Powered Assessment
        </div>
        <h1 className="hero-title">Grade papers in seconds,<br />not hours</h1>
        <p className="hero-desc">
          Upload an answer sheet and FairMark extracts each answer and grades it
          against your subject's answer key. No key yet? It drafts a model answer
          for you to review and approve before marks are awarded.
        </p>
      </section>

      {/* ---- Main content ---- */}
      <div className="home-grid">
        {/* Left — Upload */}
        <div className="upload-card">
          <div className="card-header">
            <h2>Upload Answer Sheet</h2>
          </div>

          <UploadBox
            selectedFile={selectedFile}
            previewUrl={previewUrl}
            onFileChange={handleFileChange}
            onDrop={handleDrop}
          />

          {(previewUrl || selectedFile) && (
            <div className="upload-actions">

              {error && <div className="error-banner">{error}</div>}

              {loading ? (
                <div className="loading-state">
                  <Loader className="spinner" size={20} />
                  <div>
                    <p className="loading-title">Processing…</p>
                    <p className="loading-hint">Extracting text and grading answers</p>
                  </div>
                </div>
              ) : (
                <div className="btn-row">
                  <button onClick={uploadAndGrade} className="btn btn-primary">Grade Paper</button>
                  <button onClick={resetUpload} className="btn btn-secondary">Cancel</button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right — How it works + stats */}
        <div className="sidebar">
          <div className="how-card">
            <h3>How it works</h3>
            <ol className="steps">
              <li>
                <span className="step-num">1</span>
                <div>
                  <strong>Prepare</strong>
                  <p>Use a clear photo, scan, or PDF of the answer sheet.</p>
                </div>
              </li>
              <li>
                <span className="step-num">2</span>
                <div>
                  <strong>Upload</strong>
                  <p>Drag & drop or browse - JPG, PNG, WebP, or PDF.</p>
                </div>
              </li>
              <li>
                <span className="step-num">3</span>
                <div>
                  <strong>Get Results</strong>
                  <p>Answers are graded against the answer key, with a report you can review.</p>
                </div>
              </li>
            </ol>
          </div>

        </div>
      </div>
    </div>
  );
}

export default Home;
