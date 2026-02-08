import { useState, useEffect } from 'react';

export function HealthGrid({ proxionToken, securityOnly = false }) {
    // Load cached status from localStorage for instant O(1) display
    const [status, setStatus] = useState(() => {
        try {
            const cached = localStorage.getItem('proxion_health_status');
            return cached ? JSON.parse(cached) : { mount: '...', proxy: '...', containers: [] };
        } catch {
            return { mount: '...', proxy: '...', containers: [] };
        }
    });
    const [loading, setLoading] = useState(() => !localStorage.getItem('proxion_health_status'));
    const [refreshing, setRefreshing] = useState(false);

    const fetchStatus = async () => {
        setRefreshing(true);
        try {
            const resp = await fetch("http://127.0.0.1:8788/suite/status/detail", {
                headers: { 'Proxion-Token': proxionToken }
            });
            if (resp.ok) {
                const data = await resp.json();
                setStatus(data);
                // Persist to localStorage for instant load next time
                localStorage.setItem('proxion_health_status', JSON.stringify(data));
            }
        } catch (err) {
            console.error("HealthGrid: Failed to fetch status:", err);
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useEffect(() => {
        if (proxionToken) {
            fetchStatus();
            const interval = setInterval(fetchStatus, 5000);
            return () => clearInterval(interval);
        }
    }, [proxionToken]);

    const getStatusColor = (statusText) => {
        const s = statusText.toLowerCase();
        if (s.includes('up')) return '#4CAF50';
        if (s.includes('exited')) return '#f44336';
        if (s.includes('restarting')) return '#FF9800';
        return '#888';
    };

    if (loading) return <div className="tiny-text">Loading suite metrics...</div>;

    return (
        <div className="health-grid-container">
            {!securityOnly && (
                <div className="status-row" style={{ display: 'flex', gap: '20px', marginBottom: '20px', flexWrap: 'wrap' }}>
                    <div className="status-pill" style={{
                        padding: '8px 15px',
                        borderRadius: '20px',
                        background: status.mount === 'ONLINE' ? 'rgba(76, 175, 80, 0.1)' : 'rgba(244, 67, 54, 0.1)',
                        border: `1px solid ${status.mount === 'ONLINE' ? '#4CAF50' : '#f44336'}`,
                        fontSize: '0.8rem'
                    }}>
                        📁 Unified Stash (P:): <strong>{status.mount}</strong>
                    </div>
                    <div className="status-pill" style={{
                        padding: '8px 15px',
                        borderRadius: '20px',
                        background: status.proxy === 'ONLINE' ? 'rgba(33, 150, 243, 0.1)' : 'rgba(244, 67, 54, 0.1)',
                        border: `1px solid ${status.proxy === 'ONLINE' ? '#2196F3' : '#f44336'}`,
                        fontSize: '0.8rem'
                    }}>
                        🔌 Pod Proxy: <strong>{status.proxy}</strong>
                    </div>
                    {refreshing && <div className="tiny-text" style={{ alignSelf: 'center' }}>Refreshing...</div>}
                </div>
            )}

            {status.security_hub && (
                <div className="security-hub-row" style={{ display: 'flex', gap: '15px', marginBottom: '25px', flexWrap: 'wrap' }}>
                    {Object.entries(status.security_hub).map(([hub, data]) => (
                        <div key={hub} className="security-card" style={{
                            flex: '1',
                            minWidth: '200px',
                            background: 'rgba(255, 255, 255, 0.02)',
                            border: `1px solid ${data.status === 'ONLINE' ? 'rgba(76, 175, 80, 0.3)' : '#333'}`,
                            borderRadius: '12px',
                            padding: '12px',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '5px'
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <span style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '1px', color: '#888' }}>{hub}</span>
                                <span style={{
                                    width: '8px',
                                    height: '8px',
                                    borderRadius: '50%',
                                    background: data.status === 'ONLINE' ? '#4CAF50' : '#f44336',
                                    boxShadow: data.status === 'ONLINE' ? '0 0 8px #4CAF50' : 'none'
                                }}></span>
                            </div>
                            <div style={{ fontWeight: 'bold', fontSize: '0.9rem', color: data.status === 'ONLINE' ? '#fff' : '#888' }}>
                                {hub === 'dns' ? 'Privacy Shield' : hub === 'identity' ? 'Identity Gateway' : hub.charAt(0).toUpperCase() + hub.slice(1)}
                            </div>
                            {data.metrics && (
                                <div className="metrics-box" style={{
                                    marginTop: '8px',
                                    padding: '8px',
                                    background: 'rgba(255, 255, 255, 0.05)',
                                    borderRadius: '6px',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: '4px'
                                }}>
                                    {Object.entries(data.metrics).map(([key, val]) => {
                                        const isAlert = key.includes('new_devices') && parseInt(val) > 0;
                                        return (
                                            <div key={key} style={{
                                                display: 'flex',
                                                justify_content: 'space-between',
                                                fontSize: '0.75rem',
                                                color: isAlert ? '#ff5555' : '#ccc',
                                                fontWeight: isAlert ? 'bold' : 'normal'
                                            }}>
                                                <span style={{ textTransform: 'capitalize' }}>{key.replace('_', ' ')}:</span>
                                                <span style={{ fontWeight: 'bold', color: isAlert ? '#ff5555' : '#4CAF50' }}>{val}</span>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                            <div className="tiny-text" style={{ color: '#555', marginTop: '5px' }}>
                                {data.services.join(', ')}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {!securityOnly && (
                <div className="container-cards" style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
                    gap: '15px'
                }}>
                    {status.containers.length === 0 ? (
                        <div className="tiny-text">No containers detected.</div>
                    ) : (
                        status.containers.map(container => (
                            <div key={container.name} className="container-card" style={{
                                background: 'rgba(255, 255, 255, 0.03)',
                                border: '1px solid #333',
                                borderRadius: '12px',
                                padding: '15px'
                            }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                                    <div style={{ fontWeight: 'bold', fontSize: '0.9rem', color: '#fff' }}>{container.name}</div>
                                    <div style={{
                                        fontSize: '0.7rem',
                                        padding: '2px 8px',
                                        borderRadius: '4px',
                                        background: getStatusColor(container.status),
                                        color: '#fff'
                                    }}>
                                        {container.status.includes('(') ? container.status.split('(')[0] : 'Running'}
                                    </div>
                                </div>
                                <div className="tiny-text" style={{ marginBottom: '8px', color: '#aaa', wordBreak: 'break-all' }}>
                                    📦 {container.image}
                                </div>
                                <div className="tiny-text" style={{ color: '#888' }}>
                                    🔗 {container.ports || 'Internal Only'}
                                </div>
                            </div>
                        ))
                    )}
                </div>
            )}
        </div>
    );
}
