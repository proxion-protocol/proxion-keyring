import { useState, useEffect } from 'react';
import { QRCodeCanvas as QRCode } from 'qrcode.react';

export function FederationInvite({ proxionToken }) {
    const [invites, setInvites] = useState({});
    const [step, setStep] = useState(1); // 1: Capabilities, 2: Settings, 3: QR
    const [loading, setLoading] = useState(false);
    const [newInvite, setNewInvite] = useState(null);

    // Form State
    const [selectedCaps, setSelectedCaps] = useState(['read:stash']);
    const [expiration, setExpiration] = useState('1d');
    const [label, setLabel] = useState('');

    const capabilityOptions = [
        { id: 'read:stash', name: 'Read Storage (P:)', description: 'View and download files from the Unified Stash.' },
        { id: 'manage:suite', name: 'Manage Suite', description: 'Install, start, and stop applications.' },
        { id: 'remote.control:system:host', name: 'System Control', description: 'Remote power and tunnel management.' },
        { id: 'gateway.authorize', name: 'Identity Admin', description: 'Authorize new handshakes and links.' },
        { id: 'read:system:suite', name: 'View Status', description: 'See container health and system metrics.' }
    ];

    const templates = {
        admin: { name: 'Full Admin', caps: ['*', '*'] },
        viewer: { name: 'Read Only', caps: ['read:stash', 'read:system:suite'] },
        manager: { name: 'App Manager', caps: ['manage:suite', 'read:system:suite', 'read:stash'] }
    };

    const fetchInvites = () => {
        fetch("http://127.0.0.1:8788/federation/invite/list", {
            headers: { 'Proxion-Token': proxionToken }
        })
            .then(res => res.json())
            .then(data => setInvites(data))
            .catch(err => console.error("Failed to fetch invites:", err));
    };

    useEffect(() => {
        if (proxionToken) fetchInvites();
    }, [proxionToken]);

    const handleCreate = async () => {
        setLoading(true);
        try {
            const resp = await fetch("http://127.0.0.1:8788/federation/invite/create", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Proxion-Token": proxionToken
                },
                body: JSON.stringify({
                    capabilities: selectedCaps,
                    expiration,
                    metadata: { label, created_by: 'Dashboard' }
                })
            });

            const data = await resp.json();
            if (resp.ok) {
                setNewInvite(data);
                setStep(3);
                fetchInvites();
            } else {
                alert(`Error: ${data.error}`);
            }
        } catch (err) {
            console.error("Failed to create invite:", err);
        } finally {
            setLoading(false);
        }
    };

    const handleRevoke = async (id) => {
        if (!confirm("Revoke this invitation? Link will be deactivated.")) return;
        await fetch("http://127.0.0.1:8788/federation/invite/revoke", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Proxion-Token": proxionToken
            },
            body: JSON.stringify({ invite_id: id })
        });
        fetchInvites();
    };

    const resetForm = () => {
        setStep(1);
        setNewInvite(null);
        setSelectedCaps(['read:stash']);
        setLabel('');
    };

    return (
        <div className="view-container" style={{ padding: '0' }}>
            <div className="policy-section">
                <h3>Generate Federation Invite</h3>
                <p className="tiny-text" style={{ marginBottom: '1.5rem' }}>Invite other devices or users to join your secure mesh.</p>

                {step === 1 && (
                    <div className="wizard-step">
                        <h4>Step 1: Select Capabilities</h4>
                        <div style={{ display: 'flex', gap: '10px', marginBottom: '1rem' }}>
                            {Object.entries(templates).map(([key, t]) => (
                                <button key={key} className="btn-secondary" onClick={() => setSelectedCaps(t.caps)}>
                                    {t.name}
                                </button>
                            ))}
                        </div>
                        <div className="cap-list" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '10px' }}>
                            {capabilityOptions.map(cap => (
                                <label key={cap.id} className="cap-card" style={{
                                    padding: '10px',
                                    border: '1px solid #333',
                                    borderRadius: '8px',
                                    display: 'block',
                                    cursor: 'pointer',
                                    background: selectedCaps.includes(cap.id) ? 'rgba(33, 150, 243, 0.1)' : 'transparent',
                                    borderColor: selectedCaps.includes(cap.id) ? '#2196F3' : '#333'
                                }}>
                                    <div style={{ display: 'flex', gap: '10px' }}>
                                        <input
                                            type="checkbox"
                                            checked={selectedCaps.includes(cap.id) || selectedCaps.includes('*')}
                                            disabled={selectedCaps.includes('*') && cap.id !== '*'}
                                            onChange={(e) => {
                                                if (e.target.checked) setSelectedCaps([...selectedCaps, cap.id]);
                                                else setSelectedCaps(selectedCaps.filter(c => c !== cap.id));
                                            }}
                                        />
                                        <div>
                                            <div style={{ fontWeight: 'bold', fontSize: '0.9rem' }}>{cap.name}</div>
                                            <div className="tiny-text">{cap.description}</div>
                                        </div>
                                    </div>
                                </label>
                            ))}
                            <label className="cap-card" style={{
                                padding: '10px',
                                border: '1px solid #333',
                                borderRadius: '8px',
                                display: 'block',
                                cursor: 'pointer',
                                background: selectedCaps.includes('*') ? 'rgba(244, 67, 54, 0.1)' : 'transparent',
                                borderColor: selectedCaps.includes('*') ? '#f44336' : '#333'
                            }}>
                                <div style={{ display: 'flex', gap: '10px' }}>
                                    <input
                                        type="checkbox"
                                        checked={selectedCaps.includes('*')}
                                        onChange={(e) => setSelectedCaps(e.target.checked ? ['*'] : [])}
                                    />
                                    <div>
                                        <div style={{ fontWeight: 'bold', fontSize: '0.9rem', color: '#f44336' }}>Full Root Admin</div>
                                        <div className="tiny-text">Unrestricted system access.</div>
                                    </div>
                                </div>
                            </label>
                        </div>
                        <button className="btn-primary" style={{ marginTop: '1.5rem' }} onClick={() => setStep(2)}>Next: Settings</button>
                    </div>
                )}

                {step === 2 && (
                    <div className="wizard-step">
                        <h4>Step 2: Invitation Settings</h4>
                        <div className="input-field" style={{ marginBottom: '1rem' }}>
                            <label className="tiny-text">Device Label / User Name</label>
                            <input
                                type="text"
                                value={label}
                                onChange={e => setLabel(e.target.value)}
                                placeholder="e.g. My Phone, Alice's PC"
                                style={{ width: '100%', margin: '5px 0' }}
                            />
                        </div>
                        <div className="input-field" style={{ marginBottom: '1rem' }}>
                            <label className="tiny-text">Expiration</label>
                            <select value={expiration} onChange={e => setExpiration(e.target.value)} style={{ width: '100%', margin: '5px 0' }}>
                                <option value="1h">1 Hour</option>
                                <option value="1d">1 Day</option>
                                <option value="1w">1 Week</option>
                                <option value="never">Never (10 years)</option>
                            </select>
                        </div>
                        <div style={{ display: 'flex', gap: '10px' }}>
                            <button className="btn-secondary" onClick={() => setStep(1)}>Back</button>
                            <button className="btn-primary" onClick={handleCreate} disabled={loading}>
                                {loading ? 'Creating...' : 'Generate Invitation'}
                            </button>
                        </div>
                    </div>
                )}

                {step === 3 && newInvite && (
                    <div className="wizard-step" style={{ textAlign: 'center' }}>
                        <h4>Step 3: Share Invitation</h4>
                        <div style={{ background: 'white', padding: '15px', borderRadius: '12px', display: 'inline-block', margin: '1rem 0' }}>
                            <QRCode value={`proxion://invite?id=${newInvite.id}`} size={200} />
                        </div>
                        <p className="tiny-text">Scan this code with the Proxion Mobile app.</p>
                        <div style={{ background: 'rgba(0,0,0,0.2)', padding: '10px', borderRadius: '8px', fontSize: '0.8rem', margin: '10px 0', wordBreak: 'break-all' }}>
                            <code>proxion://invite?id={newInvite.id}</code>
                        </div>
                        <button className="btn-secondary" onClick={resetForm}>Done</button>
                    </div>
                )}
            </div>

            <div className="policy-section" style={{ marginTop: '2rem' }}>
                <h3>Active Invitations</h3>
                <div className="policy-list">
                    {Object.values(invites).length === 0 ? (
                        <p className="tiny-text">No active invitations found.</p>
                    ) : (
                        Object.values(invites).reverse().map(invite => (
                            <div key={invite.id} className="device-card" style={{
                                opacity: invite.status === 'revoked' ? 0.5 : 1,
                                borderLeft: invite.status === 'revoked' ? '4px solid #666' : '4px solid #4CAF50'
                            }}>
                                <div className="device-info">
                                    <h4>{invite.metadata.label || 'Unnamed Invitation'}</h4>
                                    <p className="tiny-text">
                                        ID: {invite.id.substring(0, 8)}... |
                                        Caps: {invite.capabilities.length} |
                                        Expires: {new Date(invite.expires_at).toLocaleDateString()}
                                    </p>
                                    <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap', marginTop: '5px' }}>
                                        {invite.capabilities.map(c => (
                                            <span key={c} style={{ fontSize: '0.6rem', background: '#333', padding: '2px 6px', borderRadius: '4px' }}>{c}</span>
                                        ))}
                                    </div>
                                </div>
                                {invite.status === 'active' && (
                                    <button className="btn-logout-small" onClick={() => handleRevoke(invite.id)}>Revoke</button>
                                )}
                                {invite.status === 'revoked' && (
                                    <span className="tiny-text" style={{ fontStyle: 'italic' }}>Revoked</span>
                                )}
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
    );
}
