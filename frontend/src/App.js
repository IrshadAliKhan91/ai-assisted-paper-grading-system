import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom';
import './App.css';
import Navbar from './components/Navbar';
import Footer from './components/Footer';
import Home from './pages/Home';
import Search from './pages/Search';
import Results from './pages/Results';
import Dashboard from './pages/Dashboard';
import AnswerKey from './pages/AnswerKey';
import About from './pages/About';
import ErrorBoundary from './components/ErrorBoundary';

/**
 * M1: React Router — proper URL-based navigation.
 * currentResult is kept in state (not URL) because grading results are
 * large JSON objects returned from the API, not stored in the URL.
 * Deep-linking to /results without a result redirects to home.
 */
function AppRoutes() {
  const [currentResult, setCurrentResult] = useState(() => {
    try {
      const saved = sessionStorage.getItem('fairmark_result');
      return saved ? JSON.parse(saved) : null;
    } catch { return null; }
  });
  const navigate = useNavigate();

  // Persist result to sessionStorage so browser refresh doesn't lose it
  useEffect(() => {
    if (currentResult) {
      try {
        sessionStorage.setItem('fairmark_result', JSON.stringify(currentResult));
      } catch { /* quota exceeded — non-critical */ }
    }
  }, [currentResult]);

  const goToResults = (result) => {
    setCurrentResult(result);
    navigate('/results');
  };

  return (
    <div className="app">
      <Navbar />
      <div className="page-content">
        <ErrorBoundary>
          <Routes>
            <Route path="/"           element={<Home onResultReady={goToResults} />} />
            <Route path="/search"     element={<Search onResultSelect={goToResults} />} />
            <Route path="/results"    element={
              currentResult
                ? <Results result={currentResult} />
                : <Navigate to="/" replace />
            } />
            <Route path="/dashboard"  element={<Dashboard onResultReady={goToResults} />} />
            <Route path="/answer-key" element={<AnswerKey />} />
            <Route path="/about"      element={<About />} />
            {/* Catch-all */}
            <Route path="*"           element={<Navigate to="/" replace />} />
          </Routes>
        </ErrorBoundary>
      </div>
      <Footer />
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}

export default App;
