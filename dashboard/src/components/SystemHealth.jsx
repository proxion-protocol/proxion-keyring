import { useState } from 'react';

export function SystemHealth({ proxionToken }) {
    const [shuttingDown, setShuttingDown] = useState(false);
    const [status, setStatus] = useState(null);

    const handleShutdown = async () => {
        if (!window.confirm("Perform Secure Maintenance Shutdown? This will stop all integrations and unmount storage.")) return;

        setShuttingDown(true);
        setStatus(null);
        try {
            const resp = await fetch("http://127.0.0.1:8788/fleet/shutdown", {
                method: 'POST',
                headers: { 'Proxion-Token': proxionToken }
            });
            const data = await resp.json();
            setStatus(data);
        } catch (err) {
            console.error("SystemHealth: Shutdown failed:", err);
            setStatus({ status: 'error', error: "Shutdown sequence failed. Contact support or check thermal logs." });
        } finally {
            setShuttingDown(false);
        }
    };

    return (
        <div className="system-health-card" style={{
            background: 'rgba(255, 255, 255, 0.02)',
            borderRadius: '12px',
            padding: '20px',
            border: '1px solid #333'
        }}>
            <h4 style={{ margin: '0 0 15px 0', fontSize: '0.9rem', color: '#fff' }}>Maintenance & Safety</h4>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                <button
                    onClick={handleShutdown}
                    disabled={shuttingDown}
                    style={{
                        padding: '10px 15px',
                        background: shuttingDown ? 'rgba(255, 255, 255, 0.05)' : 'rgba(244, 67, 54, 0.1)',
                        border: `1px solid ${shuttingDown ? '#555' : '#f44336'}`,
                        color: shuttingDown ? '#888' : '#f44336',
                        borderRadius: '8px',
                        fontSize: '0.8rem',
                        cursor: shuttingDown ? 'not-allowed' : 'pointer',
                        transition: 'all 0.2s',
                        fontWeight: 'bold'
                    }}
                    onMouseOver={e => !shuttingDown && (e.currentTarget.style.background = 'rgba(244, 67, 54, 0.2)')}
                    onMouseOut={e => !shuttingDown && (e.currentTarget.style.background = 'rgba(244, 67, 54, 0.1)')}
                >
                    {shuttingDown ? "🚀 Executing Maintenance Sequence..." : "🚀 Secure Fleet Shutdown"}
                </button>
                {shuttingDown && <div className="loader tiny-text">Unmounting core volumes...</div>}
            </div>

            {status && (
                <div style={{
                    marginTop: '15px',
                    padding: '10px',
                    borderRadius: '8px',
                    background: status.status === 'error' ? 'rgba(244, 67, 54, 0.05)' : 'rgba(76, 175, 80, 0.05)',
                    border: `1px solid ${status.status === 'error' ? '#f44336' : '#4CAF50'}`,
                    fontSize: '0.75rem',
                    color: status.status === 'error' ? '#f44336' : '#4CAF50'
                }}>
                    {status.status === 'error' ? (
                        <span>⚠️ {status.error}</span>
                    ) : (
                        <span>✅ {status.status}: {status.containers?.results?.length || 0} integrations parked. Host is ready for maintenance.</span>
                    )}
                </div>
            )}
        </div>
    );
}
