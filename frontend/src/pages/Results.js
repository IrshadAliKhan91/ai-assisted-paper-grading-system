import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Download } from 'lucide-react';
import './Results.css';
import QuestionCard from '../components/QuestionCard';
import { exportResultPdf } from '../utils/pdfExport';
import { getGrade } from '../utils/gradeUtils';

function Results({ result: initialResult }) {
  const navigate = useNavigate();
  const [result, setResult] = useState(initialResult);

  // Sync state if prop changes
  useEffect(() => {
    setResult(initialResult);
  }, [initialResult]);

  const handleQuestionUpdated = (updatedQuestion) => {
    setResult(prev => {
      const newQuestions = (prev.questions || []).map(q =>
        q.id === updatedQuestion.id ? updatedQuestion : q
      );
      const newTotalMarks = newQuestions.reduce((sum, q) => sum + (q.score || 0), 0);
      const newMaxTotalMarks = newQuestions.reduce((sum, q) => sum + (q.maxScore || 0), 0);
      const newScorePercent = newMaxTotalMarks > 0 ? (newTotalMarks / newMaxTotalMarks) * 100 : 0;
      const newCorrect = newQuestions.filter(q => q.maxScore > 0 && q.score >= 0.7 * q.maxScore).length;

      return {
        ...prev,
        questions: newQuestions,
        totalMarks: Math.round(newTotalMarks * 100) / 100,
        maxTotalMarks: Math.round(newMaxTotalMarks * 100) / 100,
        score: Math.round(newScorePercent * 100) / 100,
        correctAnswers: newCorrect
      };
    });
  };

  if (!result) {
    return (
      <div className="no-result">
        <p>No results to display</p>
        <button onClick={() => navigate('/')} className="btn-go-home">
          Go to Home
        </button>
      </div>
    );
  }

  const getGradeColor = (score) => {
    if (score >= 80) return 'high';
    if (score >= 60) return 'medium';
    return 'low';
  };

  // H5: getGrade imported from gradeUtils — local copy removed

  const scoreColor = getGradeColor(result.score);

  // PDF Download handler
  const handleDownloadPDF = () => {
    try {
      exportResultPdf(result);
    } catch (err) {
      console.error('Failed to generate PDF:', err);
      alert('Failed to generate PDF. Please try again.');
    }
  };

  return (
    <div className="results-page">
      {/* Score Card */}
      <div className={`score-card ${scoreColor}`}>
        <div className="score-header">
          <div className="score-info">
            <p className="score-label">Total Score</p>
            <p className="score-value">
              {result.totalMarks != null ? `${result.totalMarks} / ${result.maxTotalMarks}` : `${result.score}%`}
            </p>
          </div>
          <div className="grade-badge">
            {getGrade(result.score)}
          </div>
        </div>

        <div className="score-stats">
          <StatItem label="Questions" value={result.totalQuestions} />
          <StatItem label="Attempted" value={result.attempted} />
          <StatItem label="Correct" value={result.correctAnswers} />
          <StatItem label="Percentage" value={`${result.score}%`} />
          {result.totalMarks != null && (
            <StatItem label="Marks" value={`${result.totalMarks}/${result.maxTotalMarks}`} />
          )}
        </div>
      </div>

      {/* Student Info */}
      <div className="student-info-card">
        <div className="student-info-header">
          <h2>Student Information</h2>
          <div className="submission-date">
            <span className="date-icon">📅</span>
            <span className="date-text">
              {result.date
                ? new Date(result.date).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
                : new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
            </span>
          </div>
        </div>
        <div className="info-grid">
          <InfoItem label="Student Name" value={result.studentName || 'Not Detected'} />
          <InfoItem label="Student ID" value={result.rollNumber || 'Not Detected'} />
          <InfoItem label="Subject" value={result.subject} />
        </div>
      </div>

      {/* Questions Analysis */}
      <div className="questions-section">
        <div className="questions-header">
          <h2>Question-wise Analysis</h2>
          <button className="export-button" onClick={handleDownloadPDF}>
            <Download size={20} />
            Export PDF
          </button>
        </div>

        <div className="questions-list">
          {result.questions && result.questions.length > 0 ? (
            result.questions.map((question) => (
              <QuestionCard 
                key={question.id} 
                question={question} 
                submissionId={result.id}
                onUpdate={handleQuestionUpdated}
              />
            ))
          ) : (
            <p className="no-questions">No question data available</p>
          )}
        </div>
      </div>

      <button onClick={() => navigate('/')} className="btn-grade-another">
        Grade Another Paper
      </button>
    </div>
  );
}

function StatItem({ label, value }) {
  return (
    <div className="stat-item">
      <p className="stat-value">{value}</p>
      <p className="stat-label">{label}</p>
    </div>
  );
}

function InfoItem({ label, value }) {
  return (
    <div className="info-item">
      <p className="info-label">{label}</p>
      <p className="info-value">{value}</p>
    </div>
  );
}

export default Results;