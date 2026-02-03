import { useState, useEffect } from 'react';

export const IdentityManager = ({ proxionToken }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    const fetchIdentityInfo = async () => {
        try {
            const resp = await fetch('http://127.0.0.1:8788/identity/keys', {
                headers: { 'Proxion-Token': proxionToken }
            });
            const json = await resp.json();
            setData(json);
        } catch (err) {
            console.error("Identity fetch failed", err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchIdentityInfo();
    }, [proxionToken]);

    if (loading) return <div className="spinner"></div>;

    return (
        <div className="center-card">
            <div className="card-header">
                <div className="icon-box identity">🔑</div>
                <div>
                    <h3>Fortress Identity</h3>
                    <p>Existential Instantiation & Key Management</p>
                </div>
                <div className="trust-badge">
                    Trust Score: {data?.trust_score}%
                </div>
            </div>

            <div className="key-display">
                <label>Active Fortress Public Key (Ed25519)</label>
                <div className="key-box">
                    <code>{data?.public_key}</code>
                </div>
            </div>

            <div className="metrics-grid">
                <div className="metric">
                    <label>Capabilities Issued</label>
                    <strong>{data?.capabilities_issued} Active</strong>
                </div>
                <div className="metric">
                    <label>Security Protocol</label>
                    <strong>SPEC v1.2 (Strict)</strong>
                </div>
            </div>

            <div className="audit-log">
                <label>Recent Capability Exercises</label>
                <div className="log-container">
                    <div className="log-entry">
                        <span className="time">16:12:43</span>
                        <span className="action">gateway.authorize</span>
                        <span className="status ok">ALLOWED</span>
                    </div>
                    <div className="log-entry">
                        <span className="time">16:10:05</span>
                        <span className="action">system.mount</span>
                        <span className="status ok">ALLOWED</span>
                    </div>
                    <div className="log-entry">
                        <span className="time">15:58:20</span>
                        <span className="action">peers.revoke</span>
                        <span className="status fail">DENIED (Manual Approval Req)</span>
                    </div>
                </div>
            </div>

        </div>
    );
};
