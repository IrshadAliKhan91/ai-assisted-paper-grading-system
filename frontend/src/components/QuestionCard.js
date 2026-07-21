
import React, { useState, useEffect, useRef } from 'react';
import { AlertTriangle, Clock, Sparkles, MessageSquare } from 'lucide-react';
import './QuestionCard.css';
import { cleanStudentAnswer, cleanQuestionText } from '../utils/textUtils';
import { api } from '../services/api';

function QuestionCard({ question, submissionId, onUpdate }) {
  const [isEditing, setIsEditing] = useState(false);
  // Don't pre-fill with placeholder text like "(Awaiting Teacher Model Answer)"
  const isPlaceholderAnswer = (question.correctAnswer || '').startsWith('(');
  const [editedAnswer, setEditedAnswer] = useState(isPlaceholderAnswer ? '' : (question.correctAnswer || ''));
  const [isEditingOcr, setIsEditingOcr] = useState(false);
  const [editedQuestion, setEditedQuestion] = useState(question.question || '');
  const [editedStudentAnswer, setEditedStudentAnswer] = useState(question.studentAnswer || '');
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const textareaRef = useRef(null);
  const ocrTextareaRef = useRef(null);

  // Teacher must approve/provide an answer key before grading can happen
  const needsAnswerApproval = [
    'ai_assisted',
    'manual_review_suggested_answer',
    'manual_review_missing_answer',
    'manual_review_grade_with_answer_error',
  ].includes(question.gradingMethod);
  const hasSuggestedAnswer = question.gradingMethod === 'manual_review_suggested_answer' && question.correctAnswer;
  const needsOcrCorrection = question.gradingMethod === 'manual_review_ocr_uncertain';

  // Sync state if prop changes
  useEffect(() => {
    const ca = question.correctAnswer || '';
    setEditedAnswer(ca.startsWith('(') ? '' : ca);
    setEditedQuestion(question.question || '');
    setEditedStudentAnswer(question.studentAnswer || '');
  }, [question.correctAnswer, question.question, question.studentAnswer]);

  // Auto-resize textarea
  useEffect(() => {
    if (isEditing && textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [editedAnswer, isEditing]);

  useEffect(() => {
    if (isEditingOcr && ocrTextareaRef.current) {
      ocrTextareaRef.current.style.height = 'auto';
      ocrTextareaRef.current.style.height = `${ocrTextareaRef.current.scrollHeight}px`;
    }
  }, [editedStudentAnswer, isEditingOcr]);

  const handleApprove = async () => {
    try {
      setIsSaving(true);
      setSaveError('');
      const updatedQuestion = await api.approveAnswer(submissionId, question.id, editedAnswer);
      if (onUpdate) onUpdate(updatedQuestion);
      setIsEditing(false);
    } catch (err) {
      console.error(err);
      setSaveError('Failed to approve answer: ' + err.message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleCorrectOcr = async () => {
    try {
      setIsSaving(true);
      setSaveError('');
      const updatedQuestion = await api.correctOcrAnswer(
        submissionId,
        question.id,
        editedQuestion,
        editedStudentAnswer
      );
      if (onUpdate) onUpdate(updatedQuestion);
      setIsEditingOcr(false);
    } catch (err) {
      console.error(err);
      setSaveError('Failed to save OCR correction: ' + err.message);
    } finally {
      setIsSaving(false);
    }
  };

  const getScoreColor = (score, max) => {
    if (!max || max === 0) return 'low';
    const percentage = (score / max) * 100;
    if (percentage >= 80) return 'high';
    if (percentage >= 50) return 'medium';
    return 'low';
  };

  const scoreColor = getScoreColor(question.score, question.maxScore);

  return (
    <div className={`question-card ${scoreColor}`}>
      <div className="question-header">
        <h3 className="question-title">
          {cleanQuestionText(question.question)}
        </h3>
        <div className={`score-badge ${scoreColor}`}>
          {question.score}/{question.maxScore}
        </div>
      </div>

      <div className="answer-comparison">
        <div className="answer-box student-answer">
          <p className="answer-label">Student's Answer</p>
          <p className="answer-text">{cleanStudentAnswer(question.studentAnswer)}</p>
        </div>

        <div className="answer-box expected-answer">
          <div className="answer-box-header">
            <p className="answer-label">Expected Answer (Reference Key)</p>
            {needsAnswerApproval && !isEditing && hasSuggestedAnswer && (
              <button className="btn-edit-small" onClick={() => setIsEditing(true)}>Edit</button>
            )}
          </div>
          {isEditing ? (
            <div className="edit-answer-container">
              <textarea
                ref={textareaRef}
                className="edit-answer-textarea"
                value={editedAnswer}
                onChange={(e) => setEditedAnswer(e.target.value)}
                placeholder="Type the correct/expected answer here..."
              />
              <div className="edit-answer-actions">
                <button className="btn btn-secondary btn-sm" onClick={() => { setIsEditing(false); setEditedAnswer(isPlaceholderAnswer ? '' : (question.correctAnswer || '')); }} disabled={isSaving}>Cancel</button>
                <button className="btn btn-primary btn-sm" onClick={handleApprove} disabled={isSaving || !editedAnswer.trim()}>
                  {isSaving ? 'Grading...' : 'Approve & Grade'}
                </button>
              </div>
            </div>
          ) : (
            <p className="answer-text">{isPlaceholderAnswer ? '—' : (question.correctAnswer || '—')}</p>
          )}
          {needsAnswerApproval && !isEditing && hasSuggestedAnswer && (
            <div className="approve-action-row">
              <button className="btn btn-primary btn-sm btn-block" onClick={handleApprove} disabled={isSaving}>
                {isSaving ? 'Approving...' : 'Approve & Grade'}
              </button>
            </div>
          )}
          {needsAnswerApproval && !isEditing && !hasSuggestedAnswer && (
            <div className="approve-action-row">
              <button className="btn btn-primary btn-sm btn-block" onClick={() => setIsEditing(true)}>
                Provide Answer Key
              </button>
            </div>
          )}
        </div>
      </div>

      {needsOcrCorrection && (
        <div className="ocr-correction-panel">
          {!isEditingOcr ? (
            <button className="btn btn-secondary btn-sm" onClick={() => setIsEditingOcr(true)}>
              Correct OCR Text
            </button>
          ) : (
            <div className="edit-answer-container">
              <input
                className="edit-answer-textarea"
                value={editedQuestion}
                onChange={(e) => setEditedQuestion(e.target.value)}
                placeholder="Correct question text"
              />
              <textarea
                ref={ocrTextareaRef}
                className="edit-answer-textarea"
                value={editedStudentAnswer}
                onChange={(e) => setEditedStudentAnswer(e.target.value)}
                placeholder="Correct student answer"
              />
              <div className="edit-answer-actions">
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => {
                    setIsEditingOcr(false);
                    setEditedQuestion(question.question || '');
                    setEditedStudentAnswer(question.studentAnswer || '');
                  }}
                  disabled={isSaving}
                >
                  Cancel
                </button>
                <button className="btn btn-primary btn-sm" onClick={handleCorrectOcr} disabled={isSaving}>
                  {isSaving ? 'Saving...' : 'Save Correction'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {question.similarityScore !== undefined && question.similarityScore > 0 && (
        <div className="similarity-row">
          <span className="similarity-label">AI Similarity</span>
          <div className="similarity-track">
            <div
              className={`similarity-fill ${scoreColor}`}
              style={{ width: `${Math.round(question.similarityScore * 100)}%` }}
            />
          </div>
          <span className="similarity-pct">{Math.round(question.similarityScore * 100)}%</span>
        </div>
      )}

      {saveError && (
        <div className="api-limit-banner" style={{color: '#b91c1c', background: '#fef2f2'}}>
          <AlertTriangle size={14} />
          <span>{saveError}</span>
        </div>
      )}

      {question.aiFeedback && (
        <div className="ai-feedback-banner">
          <MessageSquare size={14} />
          <div className="ai-feedback-content">
            <span className="ai-feedback-label">AI Feedback</span>
            <span className="ai-feedback-text">{question.aiFeedback}</span>
          </div>
        </div>
      )}

      {question.apiLimitReached && (
        <div className="api-limit-banner">
          <Clock size={14} />
          <span>AI quota exceeded — reference answer could not be generated. Please wait a few minutes and retry.</span>
        </div>
      )}

      {!question.apiLimitReached && needsAnswerApproval && hasSuggestedAnswer && (
        <div className="gemini-assisted-banner">
          <Sparkles size={14} />
          <span>
            AI-generated answer key needs your approval before grading. You can edit it first.
          </span>
        </div>
      )}

      {!question.apiLimitReached && needsAnswerApproval && !hasSuggestedAnswer && (
        <div className="manual-review-banner">
          <AlertTriangle size={14} />
          <span>
            No answer key available. Please provide the correct answer to grade this question.
          </span>
        </div>
      )}

      {/* Manual review: question could not be graded for other reasons */}
      {!question.apiLimitReached
        && !needsAnswerApproval
        && question.manualReviewRequired
        && !['nlp', 'provided_answer', 'dataset_match'].includes(question.gradingMethod) && (
        <div className="manual-review-banner">
          <AlertTriangle size={14} />
          <span>{question.fallbackReason || 'Could not grade automatically - manual review required.'}</span>
        </div>
      )}
    </div>
  );
}

export default QuestionCard;
