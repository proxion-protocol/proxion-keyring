import { useState, useEffect } from 'react';

export function FederationPolicy({ proxionToken }) {
    const [policies, setPolicies] = useState([]);
    const [loading, setLoading] = useState(false);

    const fetchPolicies = () => {
        if (!proxionToken) return;
        setLoading(true);
        fetch("http://localhost:8788/federation/policies", {
            headers: { 'Proxion-Token': proxionToken }
        })
            .then(res => res.json())
            .then(data => {
                // transform object to array
                const list = Object.values(data).filter(p => p.type === 'relationship_certificate');
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
            await fetch("http://localhost:8788/federation/revoke", {
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
                            <div key={pol.certificate.certificate_id} className="device-card policy-card"
                                style={{ borderLeft: pol.status === 'active' ? '4px solid #4caf50' : '4px solid #f44336' }}>
                                <div className="device-info">
                                    <h4>{pol.subject_id}</h4>
                                    <p style={{ fontSize: '0.8rem', color: '#888' }}>
                                        {pol.certificate.capabilities.length} Capabilities Granted
                                    </p>
                                    <div className="caps-tags">
                                        {pol.certificate.capabilities.map((cap, i) => (
                                            <span key={i} className="badge">
                                                {cap.can} @ {cap.with}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                                <div className="device-status">
                                    <span className={`dot ${pol.status === 'active' ? 'active' : ''}`}></span>
                                    {pol.status.toUpperCase()}
                                </div>
                                {pol.status === 'active' && (
                                    <button className="btn-revoke" onClick={() => handleRevoke(pol.certificate.certificate_id)} title="Revoke">
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
