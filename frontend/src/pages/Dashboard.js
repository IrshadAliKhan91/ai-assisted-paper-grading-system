import React, { useEffect, useState } from 'react';
import { Users, FileSpreadsheet, TrendingUp, BarChart3, RefreshCw } from 'lucide-react';
import './Dashboard.css';
import { api } from '../services/api';

function Dashboard() {
  const [stats, setStats] = useState({ totalStudents: 0, totalPapers: 0, averageScore: 0, successRate: 0 });
  const [activity, setActivity] = useState([]);
  const [loading, setLoading] = useState(true);
  const load = async () => {
    setLoading(true);
    const [statsData, dashboardData] = await Promise.all([api.getStats(), api.getDashboard()]);
    setStats(statsData);
    setActivity(dashboardData.recentActivity || []);
    setLoading(false);
  };
  useEffect(() => { load(); }, []);
  if (loading) return <div className="dashboard-loading"><div className="loading-spinner" /><p>Loading dashboard...</p></div>;
  return <div className="dashboard-page"><div className="dashboard-header"><h1 className="dashboard-title">Dashboard</h1><button className="refresh-btn" onClick={load} title="Refresh"><RefreshCw size={15} /></button></div><div className="stats-grid"><Stat icon={<Users size={36} />} title="Total Students" value={stats.totalStudents} /><Stat icon={<FileSpreadsheet size={36} />} title="Papers Graded" value={stats.totalPapers} /><Stat icon={<TrendingUp size={36} />} title="Average Score" value={`${stats.averageScore}%`} /><Stat icon={<BarChart3 size={36} />} title="Success Rate" value={`${stats.successRate}%`} /></div><div className="dashboard-card"><h2>Recent Activity</h2>{activity.length ? activity.map((item, i) => <div className="activity-item" key={i}><div className="activity-info"><p className="activity-name">{item.name}</p><p className="activity-time">{item.subject} · {item.time}</p></div><div className="activity-score">{item.score}%</div></div>) : <p className="empty-state">No graded papers yet.</p>}</div></div>;
}
function Stat({ icon, title, value }) { return <div className="stats-card"><div className="stats-icon">{icon}</div><p className="stats-value">{value}</p><p className="stats-title">{title}</p></div>; }
export default Dashboard;
