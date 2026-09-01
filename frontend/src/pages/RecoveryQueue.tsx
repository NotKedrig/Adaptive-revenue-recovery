import React, { useState, useEffect } from 'react';
import { QueueItem, QueueItemProps } from '../components/QueueItem';
import { CaseTimeline } from '../components/CaseTimeline';

interface Metrics {
  revenue_at_risk: number;
  revenue_recovered: number;
  recovery_rate_percent: number;
}

export const RecoveryQueue: React.FC = () => {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [liveQueue, setLiveQueue] = useState<QueueItemProps[]>([]);
  const [recoveredQueue, setRecoveredQueue] = useState<QueueItemProps[]>([]);
  const [activeTab, setActiveTab] = useState<'live' | 'recovered'>('live');
  const [selectedCase, setSelectedCase] = useState<string | null>(null);
  const [loadingDemo, setLoadingDemo] = useState(false);

  const fetchData = async () => {
    try {
      const [mRes, lRes, rRes] = await Promise.all([
        fetch('/api/metrics'),
        fetch('/api/queue'),
        fetch('/api/recovered')
      ]);
      const m = await mRes.json();
      const l = await lRes.json();
      const r = await rRes.json();
      
      setMetrics(m);
      setLiveQueue(l);
      setRecoveredQueue(r);
    } catch (error) {
      console.error("Error fetching data:", error);
    }
  };

  useEffect(() => {
    fetchData();
    // Poll every 5 seconds for simulation updates
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handlePopulateDemo = async () => {
    setLoadingDemo(true);
    try {
      await fetch('/api/demo/populate', { method: 'POST' });
      await fetchData();
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingDemo(false);
    }
  };

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(val);
  };

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1>Revenue Recovery</h1>
        <button className="btn-demo" onClick={handlePopulateDemo} disabled={loadingDemo}>
          {loadingDemo ? 'Populating...' : 'Load Demo Cases'}
        </button>
      </header>

      <section className="metrics-section">
        <div className="metric-card risk">
          <h3>Revenue at Risk</h3>
          <p className="metric-value">{metrics ? formatCurrency(metrics.revenue_at_risk) : '...'}</p>
        </div>
        <div className="metric-card recovered">
          <h3>Revenue Recovered</h3>
          <p className="metric-value">{metrics ? formatCurrency(metrics.revenue_recovered) : '...'}</p>
        </div>
        <div className="metric-card rate">
          <h3>Recovery Rate</h3>
          <p className="metric-value">{metrics ? `${metrics.recovery_rate_percent}%` : '...'}</p>
        </div>
      </section>

      <section className="queue-section">
        <div className="tabs">
          <button 
            className={`tab ${activeTab === 'live' ? 'active' : ''}`} 
            onClick={() => setActiveTab('live')}
          >
            Live Queue ({liveQueue.length})
          </button>
          <button 
            className={`tab ${activeTab === 'recovered' ? 'active' : ''}`} 
            onClick={() => setActiveTab('recovered')}
          >
            Recovered ({recoveredQueue.length})
          </button>
        </div>

        <div className="queue-list">
          {activeTab === 'live' && liveQueue.map(item => (
            <QueueItem key={item.case_id} {...item} onClick={setSelectedCase} />
          ))}
          {activeTab === 'live' && liveQueue.length === 0 && (
            <p className="empty-state">Queue is clear.</p>
          )}

          {activeTab === 'recovered' && recoveredQueue.map(item => (
            <QueueItem key={item.case_id} {...item} onClick={setSelectedCase} />
          ))}
          {activeTab === 'recovered' && recoveredQueue.length === 0 && (
            <p className="empty-state">No recovered cases yet.</p>
          )}
        </div>
      </section>

      {selectedCase && (
        <CaseTimeline caseId={selectedCase} onClose={() => setSelectedCase(null)} />
      )}
    </div>
  );
};
