import { useState, useEffect } from 'react';

export function PrivacyShield({ proxionToken }) {
    // Load cached protection status from localStorage for instant O(1) display
    const [protected_, setProtected] = useState(() => {
        try {
            const cached = localStorage.getItem('proxion_privacy_protected');
            return cached === 'true';
        } catch {
            return false;
        }
    });
    const [loading, setLoading] = useState(false);

    const fetchStatus = () => {
        fetch("http://127.0.0.1:8788/mesh/dns/status", {
            headers: { 'Proxion-Token': proxionToken }
        })
            .then(res => res.json())
            .then(data => {
                if (data.protected !== undefined) {
                    setProtected(data.protected);
                    // Persist to localStorage for instant load next time
                    localStorage.setItem('proxion_privacy_protected', String(data.protected));
                }
            })
            .catch(err => console.error("Failed to fetch DNS status:", err));
    };

    useEffect(() => {
        if (proxionToken) {
            fetchStatus();
            const interval = setInterval(fetchStatus, 10000);
            return () => clearInterval(interval);
        }
    }, [proxionToken]);

    const handleToggle = async () => {
        setLoading(true);
        const originalState = protected_;
        try {
            const resp = await fetch("http://127.0.0.1:8788/mesh/dns/toggle", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Proxion-Token": proxionToken
                },
                body: JSON.stringify({ enable: !protected_ })
            });

            if (resp.status === 202) {
                // Command sent, pending UAC
                // alert("DNS change requested. Please approve the UAC prompt if it appears on the host.");
                // We use a more subtle approach: optimistic update + background verification
                setProtected(!protected_);

                // Poll for actual success for 15 seconds
                let attempts = 0;
                const pollVerification = setInterval(async () => {
                    attempts++;
                    const check = await fetch("http://127.0.0.1:8788/mesh/dns/status", {
                        headers: { 'Proxion-Token': proxionToken }
                    });
                    const status = await check.json();

                    if (status.protected === !originalState) {
                        clearInterval(pollVerification);
                        setProtected(!originalState);
                    } else if (attempts > 15) {
                        clearInterval(pollVerification);
                        setProtected(originalState);
                        alert("UAC Request Timed Out. Please ensure you approve the permission prompt when it appears.");
                    }
                }, 1000);
            } else {
                const data = await resp.json();
                if (data.error) alert(`Error: ${data.error}`);
            }
        } catch (err) {
            console.error("Toggle failed:", err);
            setProtected(originalState);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="policy-section" style={{ marginBottom: '2rem' }}>
            <div className="device-card policy-card" style={{
                borderLeft: protected_ ? '4px solid #4CAF50' : '4px solid #F44336',
                background: protected_ ? 'rgba(76, 175, 80, 0.05)' : 'rgba(244, 67, 54, 0.05)'
            }}>
                <div className="device-info">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <span style={{ fontSize: '1.5rem' }}>{protected_ ? '🛡️' : '🔓'}</span>
                        <div>
                            <h4>Global Privacy Shield</h4>
                            <p style={{ fontSize: '0.8rem', color: '#888' }}>
                                {protected_
                                    ? "Your host is protected. All DNS traffic is filtered by local AdGuard."
                                    : "Protection disabled. Using default system DNS."}
                            </p>
                        </div>
                    </div>
                </div>

                <div className="actions">
                    <button
                        className={protected_ ? "btn-secondary" : "btn-primary"}
                        onClick={handleToggle}
                        disabled={loading}
                    >
                        {loading ? 'Processing...' : (protected_ ? 'Disable Protection' : 'Enable Privacy Shield')}
                    </button>
                </div>
            </div>
        </div>
    );
}
