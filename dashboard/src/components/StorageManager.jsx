import { useState, useEffect } from 'react';

export const StorageManager = ({ proxionToken }) => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [mounting, setMounting] = useState(false);

    const fetchStorageStats = async () => {
        try {
            const resp = await fetch('http://127.0.0.1:8788/storage/stats', {
                headers: { 'Proxion-Token': proxionToken }
            });
            const json = await resp.json();
            setData(json);
        } catch (err) {
            console.error("Storage stats fetch failed", err);
        } finally {
            setLoading(false);
        }
    };

    const handleMount = async () => {
        setMounting(true);
        try {
            const resp = await fetch('http://127.0.0.1:8788/system/mount', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Proxion-Token': proxionToken
                }
            });
            if (resp.ok) {
                setTimeout(fetchStorageStats, 2000);
            }
        } catch (err) {
            console.error("Mount request failed", err);
        } finally {
            setMounting(false);
        }
    };

    useEffect(() => {
        fetchStorageStats();
        const interval = setInterval(fetchStorageStats, 10000);
        return () => clearInterval(interval);
    }, [proxionToken]);

    if (loading) return <div className="spinner"></div>;

    const usagePercent = data?.usage?.percent || 0;
    const gbUsed = (data?.usage?.used / (1024 ** 3)).toFixed(2);
    const gbTotal = (data?.usage?.total / (1024 ** 3)).toFixed(2);

    return (
        <div className="center-card">
            <div className="card-header">
                <div className="icon-box drive">💽</div>
                <div>
                    <h3>Unified Mount (Drive P:)</h3>
                    <p>Dropbox-style FUSE integration</p>
                </div>
                <div className={`status-pill ${data?.is_mounted ? 'mounted' : 'unmounted'}`}>
                    {data?.is_mounted ? 'MOUNTED' : 'DISCONNECTED'}
                </div>
            </div>

            <div className="storage-viz-container">
                <div className="storage-label">
                    <span>Storage Utilization</span>
                    <strong>{gbUsed} GB / {gbTotal === "0.00" ? "???" : gbTotal} GB</strong>
                </div>
                <div className="progress-bg">
                    <div className="progress-fill" style={{ width: `${usagePercent}%` }}></div>
                </div>
            </div>

            <div className="metrics-grid">
                <div className="metric">
                    <label>FUSE Logic</label>
                    <strong>proxion-fuse v1.4</strong>
                </div>
                <div className="metric">
                    <label>Cache Health</label>
                    <strong className="ok">{data?.cache_health}</strong>
                </div>
                <div className="metric">
                    <label>Last Sync</label>
                    <strong>{new Date(data?.last_sync).toLocaleTimeString()}</strong>
                </div>
                <div className="metric">
                    <label>Pod Path</label>
                    <strong>/stash/</strong>
                </div>
            </div>

            <div className="card-footer">
                {!data?.is_mounted ? (
                    <button className="btn-primary w-full" onClick={handleMount} disabled={mounting}>
                        {mounting ? 'Orchestrating Mount...' : 'Mount Drive P:'}
                    </button>
                ) : (
                    <div className="hint-text">Drive P: is active in your File Explorer.</div>
                )}
            </div>

        </div>
    );
};
