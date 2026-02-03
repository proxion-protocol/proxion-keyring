import { useState, useEffect } from 'react';

export const RelayManager = ({ proxionToken }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    const fetchRelayStatus = async () => {
        try {
            const resp = await fetch('http://127.0.0.1:8788/relay/status', {
                headers: { 'Proxion-Token': proxionToken }
            });
            const json = await resp.json();
            setData(json);
        } catch (err) {
            console.error("Relay status fetch failed", err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchRelayStatus();
        const interval = setInterval(fetchRelayStatus, 5000);
        return () => clearInterval(interval);
    }, [proxionToken]);

    if (loading) return <div className="spinner"></div>;

    return (
        <div className="center-card">
            <div className="card-header">
                <div className="icon-box net">🌐</div>
                <div>
                    <h3>Mesh Relay Backbone</h3>
                    <p>Global encrypted transport layer</p>
                </div>
                <div className={`status-pill ${data?.status.toLowerCase()}`}>
                    {data?.status}
                </div>
            </div>

            <div className="metrics-grid">
                <div className="metric">
                    <label>Backbone Node</label>
                    <strong>{data?.relay_node}</strong>
                </div>
                <div className="metric">
                    <label>Latency (RTT)</label>
                    <strong className="latency">{data?.latency_ms}ms</strong>
                </div>
                <div className="metric">
                    <label>Messages Forwarded</label>
                    <strong>{data?.messages_proxied.toLocaleString()}</strong>
                </div>
                <div className="metric">
                    <label>Uptime</label>
                    <strong>{data?.uptime}</strong>
                </div>
            </div>

            <div className="throughput-viz">
                <div className="viz-bar" style={{ width: '65%' }}></div>
                <div className="viz-label">{data?.bandwidth_kbps} KB/s Current Traffic</div>
            </div>

        </div>
    );
};
