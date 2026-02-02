import { useState, useEffect } from 'react';

export function Discovery({ proxionToken }) {
    const [query, setQuery] = useState("");
    const [results, setResults] = useState([]);
    const [status, setStatus] = useState(null);
    const [audit, setAudit] = useState(null);
    const [loading, setLoading] = useState(false);

    const fetchAudit = async () => {
        try {
            const res = await fetch("http://localhost:8788/warden/audit", {
                headers: { "Proxion-Token": proxionToken }
            });
            if (res.ok) setAudit(await res.json());
        } catch (e) {
            console.error("Failed to fetch audit", e);
        }
    };

    const fetchStatus = async () => {
        try {
            const res = await fetch("http://localhost:8788/lens/status", {
                headers: { "Proxion-Token": proxionToken }
            });
            if (res.ok) setStatus(await res.json());
        } catch (e) {
            console.error("Failed to fetch status", e);
        }
    };

    const handleSearch = async (e) => {
        e.preventDefault();
        if (!query) return;
        setLoading(true);
        try {
            const res = await fetch(`http://localhost:8788/lens/search?q=${encodeURIComponent(query)}`, {
                headers: { "Proxion-Token": proxionToken }
            });
            if (res.ok) setResults(await res.json());
        } catch (e) {
            console.error("Search failed", e);
        }
        setLoading(false);
    };

    useEffect(() => {
        if (proxionToken) {
            fetchAudit();
            fetchStatus();
            const timer = setInterval(fetchAudit, 5000);
            return () => clearInterval(timer);
        }
    }, [proxionToken]);

    return (
        <div className="discovery-section">
            <h2>Proxion Intelligence</h2>

            <div className="intelligence-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                <div className="health-card card">
                    <h3>Fortress Health (Warden)</h3>
                    {audit ? (
                        <div className="audit-data">
                            <p><strong>Hostname:</strong> {audit.hostname}</p>
                            <p><strong>VPN Tunnel:</strong> <span className={audit.network.vpn === 'active' ? 'text-success' : 'text-danger'}>{audit.network.vpn}</span></p>
                            <div className="meters">
                                <p>CPU: {audit.system.cpu}%</p>
                                <p>RAM: {audit.system.ram}%</p>
                                <p>Disk: {audit.system.disk}%</p>
                            </div>
                            <p><strong>Active Peers:</strong> {audit.network.peers}</p>
                            <p><strong>Ads Blocked:</strong> {audit.warden.blocked_total}</p>
                        </div>
                    ) : <p>Loading health data...</p>}
                </div>

                <div className="lens-card card">
                    <h3>Global Search (Lens)</h3>
                    <form onSubmit={handleSearch} style={{ display: 'flex', gap: '10px' }}>
                        <input
                            type="text"
                            placeholder="Find anything in your Pod..."
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            style={{ flex: 1 }}
                        />
                        <button type="submit" disabled={loading}>Search</button>
                    </form>

                    {status && (
                        <p className="index-info" style={{ fontSize: '0.8em', color: '#666', marginTop: '10px' }}>
                            Indexed: {status.item_count} items across {status.active_mounts.length} apps.
                            {status.is_scanning && " [Scanning...]"}
                        </p>
                    )}

                    <div className="search-results" style={{ marginTop: '20px', maxHeight: '300px', overflowY: 'auto' }}>
                        {results.length > 0 ? (
                            <ul style={{ listStyle: 'none', padding: 0 }}>
                                {results.map((item, i) => (
                                    <li key={i} style={{ padding: '8px', borderBottom: '1px solid #eee' }}>
                                        <div style={{ fontWeight: 'bold' }}>{item.name}</div>
                                        <div style={{ fontSize: '0.8em', color: '#666' }}>
                                            {item.label} &bull; {item.drive}{item.path.split(item.drive)[1]}
                                        </div>
                                    </li>
                                ))}
                            </ul>
                        ) : query && !loading && <p>No results found.</p>}
                    </div>
                </div>
            </div>
        </div>
    );
}
