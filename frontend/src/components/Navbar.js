import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Home, Search, BarChart3, BookKey, Info } from 'lucide-react';
import './Navbar.css';

// M1: Uses React Router hooks — no onNavigate prop needed
function Navbar() {
  const navigate = useNavigate();
  const location = useLocation();

  const navItems = [
    { path: '/',           label: 'Home',       icon: <Home size={16} /> },
    { path: '/search',     label: 'Search',     icon: <Search size={16} /> },
    { path: '/keys',       label: 'Answer Keys', icon: <BookKey size={16} /> },
    { path: '/dashboard',  label: 'Dashboard',  icon: <BarChart3 size={16} /> },
    { path: '/about',      label: 'About',      icon: <Info size={16} /> },
  ];

  const isActive = (path) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <button className="navbar-brand" onClick={() => navigate('/')}>
          <img
            src="/FairMarkLogo.png"
            alt="FairMark Logo"
            className="brand-logo"
          />
          <span className="brand-name">FairMark</span>
        </button>

        <div className="navbar-nav">
          {navItems.map(item => (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              className={`nav-link ${isActive(item.path) ? 'active' : ''}`}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          ))}
        </div>
      </div>
    </nav>
  );
}

export default Navbar;
