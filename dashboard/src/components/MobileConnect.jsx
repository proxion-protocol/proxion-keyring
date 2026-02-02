import { useState, useEffect } from "react";
import { QRCodeCanvas as QRCode } from 'qrcode.react';

export function MobileConnect({ onClose }) {
    const [config, setConfig] = useState(null);

    useEffect(() => {
        fetch("http://localhost:8788/onboarding-config")
            .then(res => res.json())
            .then(data => {
                const wgConfig = `[Interface]
PrivateKey = ${data.client_private_key}
Address = ${data.client_address}
DNS = ${data.client_dns || '1.1.1.1'}

[Peer]
PublicKey = ${data.server_pubkey}
Endpoint = ${data.server_endpoint}
AllowedIPs = 10.0.0.0/24
PersistentKeepalive = 25`;
                setConfig(wgConfig);
            })
            .catch(err => console.error("Failed to fetch mobile config", err));
    }, []);

    return (
        <div className="modal-overlay">
            <div className="modal-content">
                <button className="close-btn" onClick={onClose}>×</button>
                <h2>Connect Mobile App</h2>
                <p>Scan this with the <strong>Proxion Mobile</strong> app to link this device.</p>

                <div className="qr-wrapper">
                    {config ? (
                        <QRCode value={config} size={256} />
                    ) : (
                        <p>Loading configuration...</p>
                    )}
                </div>

                <p className="tiny-text">This code contains your WireGuard keys and Pod Identity.</p>
            </div>
        </div>
    );
}
