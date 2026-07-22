import React, { useEffect, useState } from 'react';
import { BookKey } from 'lucide-react';
import { api } from '../services/api';
import './AnswerKey.css';

function StoredKeys() {
  const [keys, setKeys] = useState({});
  useEffect(() => { api.getQuestionBank().then((items) => setKeys(items.reduce((all, item) => { (all[item.subject] ||= []).push(item); return all; }, {}))); }, []);
  return <div className="ak-page"><div className="ak-header"><div className="ak-title-row"><BookKey size={22} className="ak-title-icon" /><h1 className="ak-title">Saved Answer Keys</h1></div><p className="ak-subtitle">Choose any of these key titles while grading a paper.</p></div><div className="ak-browser">{Object.keys(keys).length ? Object.entries(keys).map(([title, entries]) => <div className="ak-group" key={title}><div className="ak-group-header"><span className="ak-group-name">{title}</span><span className="ak-group-count">{entries.length}</span></div>{entries.map((entry) => <div className="ak-entry" key={entry.id}><p className="ak-entry-q">{entry.question}</p><p className="ak-answer-text">{entry.answer}</p></div>)}</div>) : <div className="ak-empty">No saved keys yet.</div>}</div></div>;
}
export default StoredKeys;
