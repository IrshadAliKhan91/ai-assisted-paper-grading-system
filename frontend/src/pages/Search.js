import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search as SearchIcon, Loader, User, Calendar, BookOpen, ChevronLeft, ChevronRight } from 'lucide-react';
import './Search.css';
import { api } from '../services/api';

const PAGE_SIZE = 10;

function Search({ onResultSelect }) {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searchPerformed, setSearchPerformed] = useState(false);
  // M10: Pagination state
  const [page, setPage] = useState(0);
  const [hasMore, setHasMore] = useState(false);

  const handleSearch = async (newPage = 0) => {
    if (!searchQuery.trim()) return;

    setLoading(true);
    setError('');
    setSearchPerformed(true);
    setPage(newPage);

    try {
      // M10: Pass skip/limit for pagination
      const results = await api.searchStudents(searchQuery, newPage * PAGE_SIZE, PAGE_SIZE + 1);
      // Fetch one extra to know if there's a next page
      setHasMore(results.length > PAGE_SIZE);
      setSearchResults((results || []).slice(0, PAGE_SIZE));
    } catch (err) {
      setError('Search failed. Please try again.');
      console.error('Search error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') handleSearch(0);
  };

  const viewResult = async (result) => {
    try {
      const fullResult = await api.getResult(result.id);
      onResultSelect(fullResult);
      navigate('/results');
    } catch (err) {
      setError('Failed to load result details. Please try again.');
      console.error('Failed to view result:', err);
    }
  };

  return (
    <div className="search-page">
      <div className="search-header">
        <h1>Student Results Archive</h1>
        <p>Search by Student ID or Name to view past grading reports</p>
      </div>

      <div className="search-box">
        <div className="search-input-wrapper">
          <SearchIcon className="search-icon" size={20} />
          <input
            type="text"
            className="search-input"
            placeholder="Enter Student Name or ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={handleKeyPress}
          />
          <button className="search-submit" onClick={() => handleSearch(0)}>
            Search Result
          </button>
        </div>
      </div>

      {loading && (
        <div className="search-loading">
          <Loader className="loading-spinner" size={40} />
          <p>Searching database...</p>
        </div>
      )}

      {!loading && !error && searchResults.length > 0 && (
        <div className="search-results">
          <div className="results-header">
            <p className="results-count">
              Found <strong>{searchResults.length}</strong> result{searchResults.length !== 1 ? 's' : ''}
            </p>
          </div>

          {searchResults.map((result) => (
            <div key={result.id} className="result-card" onClick={() => viewResult(result)}>
              <div className="result-info">
                <div className="result-name">{result.studentName || result.student_name || 'Unknown Student'}</div>
                <div className="result-meta">
                  <span><User size={14} /> {result.rollNumber || result.roll_number || 'No ID'}</span>
                  <span><BookOpen size={14} /> {result.subject || 'General'}</span>
                  {result.date && <span><Calendar size={14} /> {result.date}</span>}
                </div>
              </div>

              <div className="result-score">
                <div className="score-value">{result.score}%</div>
                <div className="score-label">Total Score</div>
              </div>
            </div>
          ))}

          {/* M10: Pagination controls */}
          <div className="pagination-controls" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '1rem', marginTop: '1.5rem' }}>
            <button
              className="btn btn-secondary"
              disabled={page === 0}
              onClick={() => handleSearch(page - 1)}
              style={{ padding: '0.5rem 1rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}
            >
              <ChevronLeft size={16} /> Previous
            </button>
            <span className="pagination-info" style={{ color: 'var(--text-muted)' }}>Page {page + 1}</span>
            <button
              className="btn btn-secondary"
              disabled={!hasMore}
              onClick={() => handleSearch(page + 1)}
              style={{ padding: '0.5rem 1rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}
            >
              Next <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}

      {!loading && searchPerformed && searchResults.length === 0 && !error && (
        <div className="no-results">
          <div className="no-results-icon">
            <SearchIcon size={32} />
          </div>
          <h3>No results found</h3>
          <p>We couldn't find any student matching "{searchQuery}"</p>
        </div>
      )}

      {error && (
        <div className="no-results">
          <p style={{ color: 'var(--danger)' }}>{error}</p>
        </div>
      )}
    </div>
  );
}

export default Search;