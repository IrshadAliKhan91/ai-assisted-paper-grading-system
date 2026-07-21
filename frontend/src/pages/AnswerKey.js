import React, { useState, useEffect, useCallback } from 'react';
import { Plus, Trash2, BookOpen, Upload, Filter, ChevronDown, Pencil } from 'lucide-react';
import './AnswerKey.css';
import { api } from '../services/api';

const DEFAULT_SUBJECTS = ['English Grammar', 'Science', 'Mathematics', 'Computer Science'];

function AnswerKey() {
  const [entries, setEntries] = useState([]);
  const [subjects, setSubjects] = useState(DEFAULT_SUBJECTS);
  const [filterSubject, setFilterSubject] = useState('');
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(null);

  // Add-single form
  const [addSubject, setAddSubject] = useState('');
  const [addQuestion, setAddQuestion] = useState('');
  const [addAnswer, setAddAnswer] = useState('');
  const [addError, setAddError] = useState('');
  const [addLoading, setAddLoading] = useState(false);
  const [addSuccess, setAddSuccess] = useState('');

  // Bulk import form
  const [bulkSubject, setBulkSubject] = useState('');
  const [bulkText, setBulkText] = useState('');
  const [bulkError, setBulkError] = useState('');
  const [bulkLoading, setBulkLoading] = useState(false);
  const [bulkSuccess, setBulkSuccess] = useState('');
  const [showBulk, setShowBulk] = useState(false);

  const fetchEntries = useCallback(async () => {
    setLoading(true);
    const data = await api.getQuestionBank(filterSubject || null);
    setEntries(data);
    setLoading(false);
  }, [filterSubject]);

  useEffect(() => {
    api.getSubjects().then(r => setSubjects(r.subjects || DEFAULT_SUBJECTS));
  }, []);

  useEffect(() => { fetchEntries(); }, [fetchEntries]);

  const handleAddSingle = async (e) => {
    e.preventDefault();
    setAddError('');
    setAddSuccess('');
    if (!addSubject) { setAddError('Select a subject.'); return; }
    if (!addQuestion.trim()) { setAddError('Question is required.'); return; }
    if (!addAnswer.trim()) { setAddError('Answer is required.'); return; }

    setAddLoading(true);
    try {
      const result = await api.uploadAnswerKey(addSubject, [
        { question: addQuestion.trim(), answer: addAnswer.trim() }
      ]);
      setAddSuccess(`Added ${result.added} question to "${addSubject}".`);
      setAddQuestion('');
      setAddAnswer('');
      fetchEntries();
    } catch (err) {
      setAddError(err.message || 'Upload failed.');
    } finally {
      setAddLoading(false);
    }
  };

  const handleBulkImport = async (e) => {
    e.preventDefault();
    setBulkError('');
    setBulkSuccess('');
    if (!bulkSubject) { setBulkError('Select a subject.'); return; }
    if (!bulkText.trim()) { setBulkError('Paste your Q&A pairs.'); return; }

    let questions;
    try {
      questions = parseBulkText(bulkText);
    } catch (err) {
      setBulkError(err.message);
      return;
    }

    if (questions.length === 0) { setBulkError('No valid Q&A pairs found.'); return; }

    setBulkLoading(true);
    try {
      const result = await api.uploadAnswerKey(bulkSubject, questions);
      setBulkSuccess(`Imported ${result.added} question${result.added !== 1 ? 's' : ''} into "${bulkSubject}".`);
      setBulkText('');
      fetchEntries();
    } catch (err) {
      setBulkError(err.message || 'Import failed.');
    } finally {
      setBulkLoading(false);
    }
  };

  const handleDelete = async (id) => {
    setDeleting(id);
    try {
      await api.deleteQuestionBankEntry(id);
      setEntries(prev => prev.filter(e => e.id !== id));
    } catch (err) {
      console.error('Delete failed:', err);
    } finally {
      setDeleting(null);
    }
  };

  const handleUpdate = (updated) => {
    setEntries(prev => prev.map(e => (e.id === updated.id ? { ...e, ...updated } : e)));
  };

  const grouped = groupBySubject(entries);
  const subjectKeys = Object.keys(grouped).sort();

  return (
    <div className="ak-page">
      <div className="ak-header">
        <div className="ak-title-row">
          <BookOpen size={22} className="ak-title-icon" />
          <h1 className="ak-title">Answer Key Manager</h1>
        </div>
        <p className="ak-subtitle">
          Answers are graded against the key for each subject. Questions with no
          matching key are flagged for review with an AI-drafted suggestion.
        </p>
      </div>

      <div className="ak-layout">
        {/* ── Left: Add forms ── */}
        <div className="ak-forms">
          {/* Add single */}
          <div className="ak-card">
            <h2 className="ak-card-title">
              <Plus size={16} /> Add Question
            </h2>

            <form onSubmit={handleAddSingle} className="ak-form">
              <div className="ak-field">
                <label className="ak-label">Subject</label>
                <div className="ak-select-wrap">
                  <select
                    className="ak-select"
                    value={addSubject}
                    onChange={e => setAddSubject(e.target.value)}
                  >
                    <option value="">Select subject…</option>
                    {subjects.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                  <ChevronDown size={14} className="ak-select-icon" />
                </div>
              </div>

              <div className="ak-field">
                <label className="ak-label">Question</label>
                <textarea
                  className="ak-textarea"
                  rows={3}
                  placeholder="e.g. What is photosynthesis?"
                  value={addQuestion}
                  onChange={e => setAddQuestion(e.target.value)}
                />
              </div>

              <div className="ak-field">
                <label className="ak-label">Correct Answer</label>
                <textarea
                  className="ak-textarea"
                  rows={3}
                  placeholder="e.g. Photosynthesis is the process by which plants…"
                  value={addAnswer}
                  onChange={e => setAddAnswer(e.target.value)}
                />
              </div>

              {addError && <p className="ak-msg ak-error">{addError}</p>}
              {addSuccess && <p className="ak-msg ak-success">{addSuccess}</p>}

              <button
                type="submit"
                className="btn btn-primary ak-submit"
                disabled={addLoading}
              >
                {addLoading ? 'Saving…' : 'Add Question'}
              </button>
            </form>
          </div>

          {/* Template Import */}
          <div className="ak-card">
            <button
              className="ak-card-title ak-collapsible"
              onClick={() => setShowBulk(v => !v)}
              type="button"
            >
              <Upload size={16} /> Bulk Import (Text)
              <ChevronDown size={14} className={`ak-chevron ${showBulk ? 'open' : ''}`} />
            </button>

            {showBulk && (
              <form onSubmit={handleBulkImport} className="ak-form">
                <div className="ak-field">
                  <label className="ak-label">Subject</label>
                  <div className="ak-select-wrap">
                    <select
                      className="ak-select"
                      value={bulkSubject}
                      onChange={e => setBulkSubject(e.target.value)}
                    >
                      <option value="">Select subject…</option>
                      {subjects.map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                    <ChevronDown size={14} className="ak-select-icon" />
                  </div>
                </div>

                <div className="ak-field">
                  <label className="ak-label">Paste Q&amp;A pairs</label>
                  <p className="ak-hint">
                    JSON array: <code>[{'{'}&#34;question&#34;:&#34;…&#34;,&#34;answer&#34;:&#34;…&#34;{'}'}]</code><br />
                    or one block per pair: <code>Q: …\nA: …</code>
                  </p>
                  <textarea
                    className="ak-textarea ak-textarea-tall"
                    rows={8}
                    placeholder={'[{"question":"What is X?","answer":"X is..."}]'}
                    value={bulkText}
                    onChange={e => setBulkText(e.target.value)}
                  />
                </div>

                {bulkError && <p className="ak-msg ak-error">{bulkError}</p>}
                {bulkSuccess && <p className="ak-msg ak-success">{bulkSuccess}</p>}

                <button
                  type="submit"
                  className="btn btn-primary ak-submit"
                  disabled={bulkLoading}
                >
                  {bulkLoading ? 'Importing…' : 'Import All'}
                </button>
              </form>
            )}
          </div>
          
          {/* Docx Template Upload */}
          <div className="ak-card">
            <h2 className="ak-card-title">
              <Upload size={16} /> Upload Template (.docx)
            </h2>
            <p className="ak-hint" style={{marginBottom: '1rem'}}>
              Upload your <code>.docx</code> exam template. The system will extract the Subject, Questions, and Max Marks automatically.
            </p>
            <input
                type="file"
                accept=".docx"
                onChange={async (e) => {
                  const file = e.target.files[0];
                  if (!file) return;
                  setBulkLoading(true);
                  setBulkError('');
                  setBulkSuccess('');
                  try {
                    const result = await api.uploadAnswerKey('', [], file);
                    setBulkSuccess(`Successfully processed "${result.subject}" and added ${result.added} questions!`);
                    fetchEntries();
                    e.target.value = ''; // reset file input
                  } catch (err) {
                    setBulkError(err.message || 'Template upload failed.');
                  } finally {
                    setBulkLoading(false);
                  }
                }}
                disabled={bulkLoading}
                style={{ width: '100%', marginBottom: '1rem' }}
            />
            {bulkError && <p className="ak-msg ak-error">{bulkError}</p>}
            {bulkSuccess && <p className="ak-msg ak-success">{bulkSuccess}</p>}
          </div>
        </div>

        {/* ── Right: Browse ── */}
        <div className="ak-browser">
          <div className="ak-browser-header">
            <h2 className="ak-card-title" style={{ margin: 0 }}>
              <Filter size={16} /> Browse ({entries.length} entries)
            </h2>
            <div className="ak-select-wrap ak-filter-select">
              <select
                className="ak-select"
                value={filterSubject}
                onChange={e => setFilterSubject(e.target.value)}
              >
                <option value="">All subjects</option>
                {subjects.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
              <ChevronDown size={14} className="ak-select-icon" />
            </div>
          </div>

          {loading ? (
            <div className="ak-empty">Loading…</div>
          ) : entries.length === 0 ? (
            <div className="ak-empty">
              <BookOpen size={32} className="ak-empty-icon" />
              <p>No custom questions yet.</p>
              <p className="ak-empty-hint">Add some using the form on the left.</p>
            </div>
          ) : (
            <div className="ak-groups">
              {subjectKeys.map(subj => (
                <div key={subj} className="ak-group">
                  <div className="ak-group-header">
                    <span className="ak-group-name">{subj}</span>
                    <span className="ak-group-count">{grouped[subj].length}</span>
                  </div>
                  <div className="ak-entries">
                    {grouped[subj].map(entry => (
                      <EntryRow
                        key={entry.id}
                        entry={entry}
                        onDelete={handleDelete}
                        onUpdate={handleUpdate}
                        deleting={deleting === entry.id}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function EntryRow({ entry, onDelete, onUpdate, deleting }) {
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(entry.answer || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // Keep the draft in sync if the entry changes underneath us
  useEffect(() => { setDraft(entry.answer || ''); }, [entry.answer]);

  const hasAnswer = !!(entry.answer && entry.answer.trim());

  const startEdit = (e) => {
    e.stopPropagation();
    setDraft(entry.answer || '');
    setError('');
    setEditing(true);
    setExpanded(true);
  };

  const cancelEdit = () => {
    setEditing(false);
    setDraft(entry.answer || '');
    setError('');
  };

  const saveEdit = async () => {
    setSaving(true);
    setError('');
    try {
      const updated = await api.updateQuestionBankEntry(entry.id, { answer: draft.trim() });
      onUpdate(updated);
      setEditing(false);
    } catch (err) {
      setError(err.message || 'Failed to save answer.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={`ak-entry ${expanded ? 'expanded' : ''}`}>
      <div className="ak-entry-top" onClick={() => setExpanded(v => !v)}>
        <p className="ak-entry-q">{entry.question}</p>
        <div className="ak-entry-actions">
          {!hasAnswer && <span className="ak-needs-answer" title="No model answer yet">Needs answer</span>}
          <ChevronDown size={14} className={`ak-chevron ${expanded ? 'open' : ''}`} />
          <button
            className="ak-edit-btn"
            onClick={startEdit}
            disabled={saving}
            title="Edit answer"
          >
            <Pencil size={14} />
          </button>
          <button
            className="ak-delete-btn"
            onClick={e => { e.stopPropagation(); onDelete(entry.id); }}
            disabled={deleting}
            title="Delete"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>
      {expanded && (
        <div className="ak-entry-answer">
          <span className="ak-answer-label">Answer</span>
          {editing ? (
            <div className="ak-answer-edit" onClick={e => e.stopPropagation()}>
              <textarea
                className="ak-textarea"
                rows={3}
                value={draft}
                onChange={e => setDraft(e.target.value)}
                placeholder="Type the model answer for this question…"
                autoFocus
              />
              {error && <p className="ak-msg ak-error">{error}</p>}
              <div className="ak-answer-edit-actions">
                <button className="btn btn-secondary btn-sm" onClick={cancelEdit} disabled={saving}>
                  Cancel
                </button>
                <button className="btn btn-primary btn-sm" onClick={saveEdit} disabled={saving}>
                  {saving ? 'Saving…' : 'Save Answer'}
                </button>
              </div>
            </div>
          ) : hasAnswer ? (
            <p className="ak-answer-text">{entry.answer}</p>
          ) : (
            <p className="ak-answer-text ak-answer-empty">
              No model answer yet — click&nbsp;
              <button className="ak-inline-link" onClick={startEdit}>Edit</button>
              &nbsp;to add one. Until then this question is graded as manual review.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function groupBySubject(entries) {
  return entries.reduce((acc, e) => {
    const key = e.subject || 'Uncategorized';
    if (!acc[key]) acc[key] = [];
    acc[key].push(e);
    return acc;
  }, {});
}

function parseBulkText(text) {
  const trimmed = text.trim();

  // Try JSON first
  if (trimmed.startsWith('[')) {
    const parsed = JSON.parse(trimmed); // throws on bad JSON
    if (!Array.isArray(parsed)) throw new Error('Expected a JSON array.');
    return parsed.map((item, i) => {
      const q = (item.question || item.q || '').trim();
      const a = (item.answer || item.a || '').trim();
      if (!q || !a) throw new Error(`Item ${i + 1} is missing question or answer.`);
      return { question: q, answer: a };
    });
  }

  // Plain text: split by blank line, each block has "Q: …\nA: …"
  const blocks = trimmed.split(/\n\s*\n/).filter(Boolean);
  return blocks.map((block, i) => {
    const qMatch = block.match(/^Q\s*:\s*(.+)/im);
    const aMatch = block.match(/^A\s*:\s*([\s\S]+)/im);
    if (!qMatch || !aMatch) throw new Error(`Block ${i + 1}: expected "Q: …" and "A: …" lines.`);
    return { question: qMatch[1].trim(), answer: aMatch[1].trim() };
  });
}

export default AnswerKey;
