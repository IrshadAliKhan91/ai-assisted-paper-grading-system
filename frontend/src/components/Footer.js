import React from 'react';
import { useNavigate } from 'react-router-dom';
import './Footer.css';

// M1: Uses React Router — no onNavigate prop needed
function Footer() {
  const navigate = useNavigate();

  const handleNav = (path) => (e) => {
    e.preventDefault();
    navigate(path);
  };

  return (
    <footer className="footer">
      <div className="footer-inner">
        <div className="footer-left">
          <div className="footer-brand">
            <img src="/FairMarkLogo.png" alt="FairMark" className="footer-logo" />
            <span className="footer-brand-name">FairMark</span>
          </div>
          <p className="footer-tagline">
            AI-powered assessment platform for modern educators.
          </p>
        </div>

        <div className="footer-links">
          <div className="footer-col">
            <h4>Product</h4>
            <a href="/" onClick={handleNav('/')}>AI Grading</a>
            <a href="/dashboard" onClick={handleNav('/dashboard')}>Analytics</a>
            <a href="/search" onClick={handleNav('/search')}>Search Records</a>
          </div>
          <div className="footer-col">
            <h4>Resources</h4>
            <a href="/answer-key" onClick={handleNav('/answer-key')}>Answer Key</a>
            <a href="/about" onClick={handleNav('/about')}>About</a>
          </div>
        </div>
      </div>

      <div className="footer-bottom">
        <span>&copy; 2026 FairMark. All rights reserved.</span>
        <span className="footer-credits">
          Built by Irshad Ali Khan, Sadiq Mansoor &amp; Wisal Ahmad
        </span>
      </div>
    </footer>
  );
}

export default Footer;
