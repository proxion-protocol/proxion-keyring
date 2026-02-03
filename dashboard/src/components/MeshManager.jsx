import { useState, useEffect } from 'react';

export function MeshManager({ proxionToken, peers }) {
    const [groups, setGroups] = useState({});
    const [newGroupName, setNewGroupName] = useState("");
    const [selectedPeer, setSelectedPeer] = useState("");

    const fetchGroups = () => {
        fetch("http://127.0.0.1:8788/mesh/list", {
            headers: { 'Proxion-Token': proxionToken }
        })
            .then(res => res.json())
            .then(data => setGroups(data))
            .catch(err => console.error(err));
    };

    useEffect(() => {
        if (proxionToken) fetchGroups();
    }, [proxionToken]);

    const handleCreate = async () => {
        if (!newGroupName) return;
        await fetch("http://127.0.0.1:8788/mesh/create", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Proxion-Token": proxionToken
            },
            body: JSON.stringify({ name: newGroupName })
        });
        setNewGroupName("");
        fetchGroups();
    };

    const handleJoin = async (groupId) => {
        if (!selectedPeer) return;
        await fetch("http://127.0.0.1:8788/mesh/join", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Proxion-Token": proxionToken
            },
            body: JSON.stringify({
                group_id: groupId,
                peer_pubkey: selectedPeer
            })
        });
        fetchGroups();
    };

    return (
        <div className="policy-section" style={{ marginTop: '2rem' }}>
            <h3>Mesh Groups (Active LANs)</h3>

            <div className="input-wrapper" style={{ display: 'flex', gap: '10px' }}>
                <input
                    type="text"
                    value={newGroupName}
                    onChange={e => setNewGroupName(e.target.value)}
                    placeholder="New Group Name"
                />
                <button className="btn-secondary" onClick={handleCreate}>+ Create</button>
            </div>

            <div className="policy-list">
                {Object.entries(groups).map(([gid, group]) => (
                    <div key={gid} className="device-card policy-card" style={{ borderLeft: '4px solid #2196F3' }}>
                        <div className="device-info">
                            <h4>{group.name}</h4>
                            <p style={{ fontSize: '0.8rem', color: '#888' }}>
                                {group.members.length} Members | {group.created_at.split('T')[0]}
                            </p>
                        </div>

                        <div className="actions" style={{ display: 'flex', gap: '5px' }}>
                            <select onChange={e => setSelectedPeer(e.target.value)} value={selectedPeer}>
                                <option value="">Add Peer...</option>
                                {Object.entries(peers).map(([pk, meta]) => (
                                    <option key={pk} value={pk}>{meta.name || pk.substring(0, 8)}</option>
                                ))}
                            </select>
                            <button className="btn-secondary" onClick={() => handleJoin(gid)}>+</button>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
