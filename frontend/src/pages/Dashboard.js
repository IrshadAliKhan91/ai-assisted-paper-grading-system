import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Users, FileSpreadsheet, TrendingUp, BarChart3, RefreshCw } from 'lucide-react';
import './Dashboard.css';
import { api } from '../services/api';

function Dashboard({ onResultReady }) {
  const navigate = useNavigate();
  const [stats, setStats] = useState({ totalStudents: 0, totalPapers: 0, averageScore: 0, successRate: 0 });
  const [dashboard, setDashboard] = useState({ recentActivity: [], topPerformers: [], subjectStats: [] });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [fetchError, setFetchError] = useState('');

  useEffect(() => { fetchAll(); }, []);

  const fetchAll = async (isRefresh = false) => {
    isRefresh ? setRefreshing(true) : setLoading(true);
    setFetchError('');
    try {
      const [statsData, dashData] = await Promise.all([
        api.getStats(),
        api.getDashboard()
      ]);
      setStats(statsData);
      setDashboard(dashData);
    } catch (err) {
      console.error('Failed to fetch dashboard:', err);
      setFetchError('Could not load dashboard data. Check your connection and try again.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  if (loading) {
    return (
      <div className="dashboard-loading">
        <div className="loading-spinner"></div>
        <p>Loading dashboard...</p>
      </div>
    );
  }

  const subjectColors = ['#3b82f6', '#10b981', '#8b5cf6', '#f59e0b', '#ef4444', '#06b6d4'];

  return (
    <div className="dashboard-page">
      <div className="dashboard-header">
        <h1 className="dashboard-title">Dashboard & Analytics</h1>
        <button
          className="refresh-btn"
          onClick={() => fetchAll(true)}
          disabled={refreshing}
          title="Refresh"
        >
          <RefreshCw size={15} className={refreshing ? 'spin' : ''} />
        </button>
        {fetchError && <p style={{color: '#dc2626', fontSize: '0.875rem', margin: '0.5rem 0 0'}}>{fetchError}</p>}
      </div>

      {/* Stats Cards */}
      <div className="stats-grid">
        <StatsCard icon={<Users size={36} />}        title="Total Students"  value={stats.totalStudents}          color="blue"   />
        <StatsCard icon={<FileSpreadsheet size={36} />} title="Papers Graded" value={stats.totalPapers}           color="green"  />
        <StatsCard icon={<TrendingUp size={36} />}   title="Average Score"  value={`${stats.averageScore}%`}     color="yellow" />
        <StatsCard icon={<BarChart3 size={36} />}    title="Success Rate"   value={`${stats.successRate}%`}      color="purple" />
      </div>

      {/* Activity and Performers */}
      <div className="dashboard-grid">
        {/* Recent Activity */}
        <div className="dashboard-card">
          <h2>Recent Activity</h2>
          {dashboard.recentActivity.length === 0 ? (
            <p className="empty-state">No graded papers yet.</p>
          ) : (
            <div className="activity-list">
              {dashboard.recentActivity.map((item, i) => (
                <div
                  key={i}
                  className="activity-item clickable"
                  onClick={() => {
                    if (item.submissionId) {
                      api.getResult(item.submissionId)
                        .then(result => { onResultReady(result); navigate('/results'); })
                        .catch(() => {});
                    }
                  }}
                >
                  <div className="activity-info">
                    <p className="activity-name">{item.name}</p>
                    <p className="activity-time">{item.subject} · {item.time}</p>
                  </div>
                  <div className={`activity-score ${item.score >= 70 ? 'good' : item.score >= 50 ? 'ok' : 'low'}`}>
                    {item.score}%
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Top Performers */}
        <div className="dashboard-card">
          <h2>Top Performers</h2>
          {dashboard.topPerformers.length === 0 ? (
            <p className="empty-state">No data yet.</p>
          ) : (
            <div className="performers-list">
              {dashboard.topPerformers.map((p, i) => (
                <div key={i} className="performer-item">
                  <div className="performer-rank">{i + 1}</div>
                  <div className="performer-info">
                    <p className="performer-name">{p.name}</p>
                    <p className="performer-papers">{p.papers} paper{p.papers !== 1 ? 's' : ''}</p>
                  </div>
                  <div className="performer-score">{p.score}%</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Subject Performance */}
      <div className="dashboard-card full-width">
        <h2>Subject Performance</h2>
        {dashboard.subjectStats.length === 0 ? (
          <p className="empty-state">No subject data yet — grade some papers first.</p>
        ) : (
          <div className="subject-bars">
            {dashboard.subjectStats.map((s, i) => (
              <SubjectBar
                key={s.subject}
                subject={s.subject}
                percentage={s.avgScore}
                count={s.count}
                color={subjectColors[i % subjectColors.length]}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatsCard({ icon, title, value, color }) {
  const palette = {
    blue:   { bg: 'linear-gradient(135deg,#3b82f6,#2563eb)', shadow: 'rgba(59,130,246,0.35)' },
    green:  { bg: 'linear-gradient(135deg,#10b981,#059669)', shadow: 'rgba(16,185,129,0.35)' },
    yellow: { bg: 'linear-gradient(135deg,#f59e0b,#d97706)', shadow: 'rgba(245,158,11,0.35)' },
    purple: { bg: 'linear-gradient(135deg,#8b5cf6,#7c3aed)', shadow: 'rgba(139,92,246,0.35)' }
  };
  return (
    <div className="stats-card" style={{ background: palette[color].bg, boxShadow: `0 8px 24px ${palette[color].shadow}` }}>
      <div className="stats-icon">{icon}</div>
      <p className="stats-value">{value}</p>
      <p className="stats-title">{title}</p>
    </div>
  );
}

function SubjectBar({ subject, percentage, count, color }) {
  return (
    <div className="subject-bar">
      <div className="subject-header">
        <span className="subject-name">{subject}</span>
        <span className="subject-meta">
          <span className="subject-count">{count} paper{count !== 1 ? 's' : ''}</span>
          <span className="subject-percentage">{percentage}%</span>
        </span>
      </div>
      <div className="progress-bar-container">
        <div className="progress-bar-fill" style={{ width: `${Math.min(percentage, 100)}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

export default Dashboard;
