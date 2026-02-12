import { useState, useEffect } from 'react';

export function FederationPolicy({ proxionToken }) {
    const [policies, setPolicies] = useState([]);
    const [loading, setLoading] = useState(false);

    const fetchPolicies = () => {
        if (!proxionToken) return;
        setLoading(true);
        fetch("http://127.0.0.1:8788/federation/policies", {
            headers: { 'Proxion-Token': proxionToken }
        })
            .then(res => res.json())
            .then(list => {
                setPolicies(list);
                setLoading(false);
            })
            .catch(err => {
                console.error("Policy fetch error:", err);
                setLoading(false);
            });
    };

    useEffect(() => {
        fetchPolicies();
        const interval = setInterval(fetchPolicies, 10000);
        return () => clearInterval(interval);
    }, [proxionToken]);

    const handleRevoke = async (certId) => {
        if (!window.confirm("Revoke this relationship? The peer will lose access immediately.")) return;

        try {
            await fetch("http://127.0.0.1:8788/federation/revoke", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Proxion-Token": proxionToken
                },
                body: JSON.stringify({ certificate_id: certId })
            });
            fetchPolicies(); // refresh
        } catch (err) {
            alert("Revoke failed: " + err.message);
        }
    };

    return (
        <div className="policy-section" style={{ marginTop: '2rem' }}>
            <h3>Federation Policies</h3>
            {loading && policies.length === 0 ? <p>Loading policies...</p> : (
                <div className="policy-list">
                    {policies.length === 0 ? (
                        <p className="empty-msg">No active federation relationships.</p>
                    ) : (
                        policies.map(pol => (
                            <div key={pol.id} className="device-card policy-card"
                                style={{ borderLeft: pol.status === 'active' ? '4px solid #4caf50' : '4px solid #f44336' }}>
                                <div className="device-info">
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                        <span style={{ fontSize: '0.7rem', padding: '2px 6px', background: pol.type === 'mesh_peer' ? '#3b82f6' : '#88c0d0', borderRadius: '4px', color: '#111' }}>
                                            {pol.type === 'mesh_peer' ? 'MESH' : 'SHARE'}
                                        </span>
                                        <h4>{pol.label}</h4>
                                    </div>
                                    <p style={{ fontSize: '0.8rem', color: '#888', marginTop: '4px' }}>
                                        ID: {pol.id.substring(0, 16)}...
                                    </p>
                                    <div className="caps-tags" style={{ display: 'flex', gap: '5px', flexWrap: 'wrap', marginTop: '8px' }}>
                                        {pol.caps.map((cap, i) => (
                                            <span key={i} className="badge" style={{ fontSize: '0.7rem', background: '#333', padding: '2px 6px', borderRadius: '4px' }}>
                                                {cap}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                                <div className="device-status">
                                    <span className={`dot ${pol.status === 'active' ? 'active' : ''}`}></span>
                                    {pol.status.toUpperCase()}
                                </div>
                                {pol.status === 'active' && (
                                    <button className="btn-revoke" onClick={() => handleRevoke(pol.id)} title="Revoke">
                                        ×
                                    </button>
                                )}
                            </div>
                        ))
                    )}
                </div>
            )}
        </div>
    );
}
