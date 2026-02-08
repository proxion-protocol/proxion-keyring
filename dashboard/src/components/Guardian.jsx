import { useState, useEffect } from 'react';
import { SecurityMetrics } from './SecurityMetrics';

export function Guardian({ proxionToken }) {
    const [stats, setStats] = useState({
        fleet_health: 0,
        status: 'BOOTING',
        last_run: null,
        repairs: 0,
        security_council: {}
    });
    const [canaryStatus, setCanaryStatus] = useState(null);
    const [networkAudit, setNetworkAudit] = useState(null);
    const [loading, setLoading] = useState(true);

    const fetchStats = async () => {
        try {
            const resp = await fetch("http://127.0.0.1:8788/network/medic/stats", {
                headers: { 'Proxion-Token': proxionToken }
            });
            if (resp.ok) {
                const data = await resp.json();
                setStats(data);
            }
        } catch (err) {
            console.error("Security: Failed to fetch stats:", err);
        } finally {
            setLoading(false);
        }
    };

    const fetchCanaryStatus = async () => {
        try {
            const resp = await fetch("http://127.0.0.1:8788/system/security/canary-status", {
                headers: { 'Proxion-Token': proxionToken }
            });
            if (resp.ok) {
                const data = await resp.json();
                if (data.status !== "NO_CANARY") {
                    setCanaryStatus(data);
                }
            }
        } catch (err) {
            console.error("Security: Failed to fetch canary status:", err);
        }
    };

    const fetchNetworkAudit = async () => {
        try {
            const resp = await fetch("http://127.0.0.1:8788/system/security/network-audit", {
                headers: { 'Proxion-Token': proxionToken }
            });
            if (resp.ok) {
                const data = await resp.json();
                setNetworkAudit(data);
            }
        } catch (err) {
            console.error("Security: Failed to fetch network audit:", err);
        }
    };

    useEffect(() => {
        if (proxionToken) {
            fetchStats();
            fetchCanaryStatus();
            fetchNetworkAudit();
            const isForging = stats.status.startsWith('FORGING');
            const interval = setInterval(() => {
                fetchStats();
                fetchCanaryStatus();
            }, isForging ? 2000 : 10000);
            return () => clearInterval(interval);
        }
    }, [proxionToken, stats.status]);

    const getHealthColor = (score) => {
        if (score >= 90) return '#4CAF50';
        if (score >= 70) return '#FF9800';
        return '#f44336';
    };

    if (loading) return <div className="tiny-text">Accessing Security Vault...</div>;

    return (
        <div className="security-container" style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '20px'
        }}>
            {/* Fleet Health Overview */}
            <div style={{
                background: 'rgba(255, 255, 255, 0.02)',
                border: '1px solid #333',
                borderRadius: '16px',
                padding: '25px',
                position: 'relative',
                overflow: 'hidden'
            }}>
                {/* Background Glow */}
                <div style={{
                    position: 'absolute',
                    top: '-100px',
                    right: '-100px',
                    width: '300px',
                    height: '300px',
                    background: `radial-gradient(circle, ${getHealthColor(stats.fleet_health)}22 0%, transparent 70%)`,
                    pointerEvents: 'none'
                }}></div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                        <h2 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 'bold', color: '#fff' }}>Fleet Security</h2>
                        <p style={{ margin: '5px 0 0 0', fontSize: '0.85rem', color: '#888' }}>
                            Autonomous security enforcement & immutable integrity checks.
                        </p>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                        <div style={{
                            fontSize: '2.5rem',
                            fontWeight: '900',
                            color: getHealthColor(stats.fleet_health),
                            textShadow: `0 0 15px ${getHealthColor(stats.fleet_health)}44`
                        }}>
                            {stats.fleet_health}%
                        </div>
                        <div style={{ fontSize: '0.7rem', color: '#555', textTransform: 'uppercase', letterSpacing: '1px' }}>
                            Fleet Safety Score
                        </div>
                    </div>
                </div>

                <div className="stats-grid" style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                    gap: '15px',
                    marginTop: '20px'
                }}>
                    <div className="stat-card" style={statCardStyle}>
                        <span style={labelStyle}>Operational Status</span>
                        <span style={{ ...valueStyle, color: stats.status === 'HEALTHY' ? '#4CAF50' : '#FF9800' }}>
                            {stats.status}
                        </span>
                    </div>
                    <div className="stat-card" style={statCardStyle}>
                        <span style={labelStyle}>Critical CVEs</span>
                        <span style={{ ...valueStyle, color: '#f44336' }}>
                            {stats.security_council?.total_critical || 0}
                        </span>
                    </div>
                    <div className="stat-card" style={statCardStyle}>
                        <span style={labelStyle}>High CVEs</span>
                        <span style={{ ...valueStyle, color: '#FF9800' }}>
                            {stats.security_council?.total_high || 0}
                        </span>
                    </div>
                    <div className="stat-card" style={statCardStyle}>
                        <span style={labelStyle}>Auto-Repairs</span>
                        <span style={{ ...valueStyle, color: '#4CAF50' }}>
                            {stats.repairs || 0}
                        </span>
                    </div>
                </div>
            </div>

            {/* Canary Deployment Status */}
            {canaryStatus && (
                <div style={{
                    background: 'rgba(255, 165, 0, 0.1)',
                    border: '1px solid #FF9800',
                    borderRadius: '12px',
                    padding: '20px'
                }}>
                    <h3 style={{ margin: '0 0 10px 0', color: '#FF9800', fontSize: '1.1rem' }}>
                        🕐 Canary Deployment Active
                    </h3>
                    <p style={{ margin: '5px 0', color: '#ccc' }}>
                        <strong>{canaryStatus.container}</strong> is under 24h monitoring
                    </p>
                    {canaryStatus.time_remaining && (
                        <p style={{ margin: '5px 0', color: '#888', fontSize: '0.85rem' }}>
                            Time remaining: {canaryStatus.time_remaining}
                        </p>
                    )}
                    {canaryStatus.ready_for_fleet_rollout && (
                        <div style={{ marginTop: '10px', color: '#4CAF50' }}>
                            ✓ Monitoring complete - Ready for fleet rollout
                        </div>
                    )}
                </div>
            )}

            {/* Network Segmentation Audit */}
            {networkAudit && (
                <div style={{
                    background: 'rgba(255, 255, 255, 0.02)',
                    border: '1px solid #333',
                    borderRadius: '12px',
                    padding: '20px'
                }}>
                    <h3 style={{ margin: '0 0 15px 0', color: '#fff', fontSize: '1.1rem' }}>
                        Network Segmentation
                    </h3>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px' }}>
                        <div style={{ ...segmentCardStyle, borderColor: '#4CAF50' }}>
                            <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#4CAF50' }}>
                                {networkAudit.compliant?.length || 0}
                            </div>
                            <div style={{ fontSize: '0.75rem', color: '#888' }}>Compliant</div>
                        </div>
                        <div style={{ ...segmentCardStyle, borderColor: '#FF9800' }}>
                            <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#FF9800' }}>
                                {networkAudit.non_compliant?.length || 0}
                            </div>
                            <div style={{ fontSize: '0.75rem', color: '#888' }}>Non-Compliant</div>
                        </div>
                        <div style={{ ...segmentCardStyle, borderColor: '#f44336' }}>
                            <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#f44336' }}>
                                {networkAudit.unassigned?.length || 0}
                            </div>
                            <div style={{ fontSize: '0.75rem', color: '#888' }}>Unassigned</div>
                        </div>
                    </div>
                </div>
            )}

            {/* Security Metrics Dashboard */}
            <SecurityMetrics proxionToken={proxionToken} />
        </div>
    );
}

const statCardStyle = {
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

const segmentCardStyle = {
    background: 'rgba(255, 255, 255, 0.03)',
    padding: '15px',
    borderRadius: '8px',
    borderLeft: '3px solid',
    textAlign: 'center'
};
