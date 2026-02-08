import { useState, useEffect } from 'react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export function SecurityMetrics({ proxionToken }) {
    const [metrics, setMetrics] = useState({
        mttr_critical: 0,
        mttr_high: 0,
        success_rate_30d: 0,
        forge_history: [],
        top_packages: []
    });

    useEffect(() => {
        const fetchMetrics = async () => {
            try {
                const resp = await fetch("http://127.0.0.1:8788/network/medic/stats", {
                    headers: { 'Proxion-Token': proxionToken }
                });
                if (resp.ok) {
                    const data = await resp.json();
                    if (data.metrics) {
                        setMetrics(data.metrics);
                    }
                }
            } catch (err) {
                console.error("SecurityMetrics: Failed to fetch:", err);
            }
        };

        if (proxionToken) {
            fetchMetrics();
            const interval = setInterval(fetchMetrics, 10000);
            return () => clearInterval(interval);
        }
    }, [proxionToken]);

    // Format MTTR (seconds to human-readable)
    const formatMTTR = (seconds) => {
        if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
        if (seconds < 86400) return `${Math.round(seconds / 3600)}h`;
        return `${Math.round(seconds / 86400)}d`;
    };

    return (
        <div className="security-metrics" style={{
            background: 'rgba(255, 255, 255, 0.02)',
            border: '1px solid #333',
            borderRadius: '16px',
            padding: '25px',
            marginTop: '20px'
        }}>
            <h2 style={{ margin: '0 0 20px 0', fontSize: '1.3rem', color: '#fff' }}>Security Metrics</h2>

            {/* MTTR Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '15px', marginBottom: '25px' }}>
                <div style={metricCardStyle}>
                    <span style={labelStyle}>MTTR (Critical)</span>
                    <span style={{ ...valueStyle, color: '#f44336' }}>{formatMTTR(metrics.mttr_critical)}</span>
                </div>
                <div style={metricCardStyle}>
                    <span style={labelStyle}>MTTR (High)</span>
                    <span style={{ ...valueStyle, color: '#FF9800' }}>{formatMTTR(metrics.mttr_high)}</span>
                </div>
                <div style={metricCardStyle}>
                    <span style={labelStyle}>Forge Success Rate (30d)</span>
                    <span style={{ ...valueStyle, color: '#4CAF50' }}>{(metrics.success_rate_30d * 100).toFixed(1)}%</span>
                </div>
            </div>

            {/* Vulnerability Trend Chart */}
            {metrics.forge_history && metrics.forge_history.length > 0 && (
                <div style={{ marginBottom: '25px' }}>
                    <h3 style={{ fontSize: '0.9rem', color: '#888', marginBottom: '10px' }}>Vulnerability Trend (Last 30 Days)</h3>
                    <ResponsiveContainer width="100%" height={200}>
                        <LineChart data={metrics.forge_history}>
                            <XAxis dataKey="date" stroke="#555" style={{ fontSize: '0.7rem' }} />
                            <YAxis stroke="#555" style={{ fontSize: '0.7rem' }} />
                            <Tooltip contentStyle={{ background: '#1a1a1a', border: '1px solid #333' }} />
                            <Line type="monotone" dataKey="critical" stroke="#f44336" strokeWidth={2} />
                            <Line type="monotone" dataKey="high" stroke="#FF9800" strokeWidth={2} />
                            <Line type="monotone" dataKey="medium" stroke="#FFC107" strokeWidth={2} />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            )}

            {/* Top Vulnerable Packages */}
            {metrics.top_packages && metrics.top_packages.length > 0 && (
                <div>
                    <h3 style={{ fontSize: '0.9rem', color: '#888', marginBottom: '10px' }}>Top 5 Vulnerable Packages</h3>
                    <ResponsiveContainer width="100%" height={200}>
                        <BarChart data={metrics.top_packages}>
                            <XAxis dataKey="package" stroke="#555" style={{ fontSize: '0.7rem' }} />
                            <YAxis stroke="#555" style={{ fontSize: '0.7rem' }} />
                            <Tooltip contentStyle={{ background: '#1a1a1a', border: '1px solid #333' }} />
                            <Bar dataKey="count" fill="#f44336" />
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            )}
        </div>
    );
}

const metricCardStyle = {
    background: 'rgba(255, 255, 255, 0.03)',
    padding: '15px',
    borderRadius: '12px',
    display: 'flex',
    flexDirection: 'column',
    gap: '5px',
    border: '1px solid rgba(255, 255, 255, 0.05)'
};

const labelStyle = {
    fontSize: '0.65rem',
    color: '#666',
    textTransform: 'uppercase',
    letterSpacing: '1px'
};

const valueStyle = {
    fontSize: '1.5rem',
    fontWeight: 'bold',
    color: '#eee'
};
