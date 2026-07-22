import React from 'react';
import './Footer.css';

// M1: Uses React Router — no onNavigate prop needed
function Footer() {
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
