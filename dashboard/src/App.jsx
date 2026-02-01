import { useEffect, useState } from 'react';
import { auth, data } from './services/solid';
import './App.css';

function App() {
  const [session, setSession] = useState(null);
  const [oidcIssuer, setOidcIssuer] = useState("https://solidcommunity.net");
  const [tunnels, setTunnels] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    auth.handleRedirect().then((sess) => {
      setSession(sess);
      setLoading(false);
      if (sess.info.isLoggedIn) {
        // Poll for active devices (Mock for now, would fetch from RS/Pod)
        setTunnels([
          { id: "dev-1", name: "Antigravity VS Code", ip: "10.0.0.3", status: "Active", lastSeen: "Just now" }
        ]);
      }
    });
  }, []);

  const handleLogin = async (e) => {
    e.preventDefault();
    await auth.login(oidcIssuer);
  };

  const handleLogout = async () => {
    await auth.logout();
    setSession(null);
  };

  if (loading) return (
    <div className="center-screen">
      <div className="spinner"></div>
    </div>
  );

  return (
    <div className="app-container">
      {!session?.info.isLoggedIn ? (
        <div className="login-card">
          <div className="brand">
            <div className="logo-icon"></div>
            <h1>proxion-keyring</h1>
          </div>
          <p className="tagline">Your personal secure cloud network.</p>

          <form onSubmit={handleLogin} className="login-form">
            <label>Connect with your Solid Pod</label>
            <div className="input-wrapper">
              <input
                type="text"
                value={oidcIssuer}
                onChange={(e) => setOidcIssuer(e.target.value)}
                placeholder="https://solidcommunity.net"
              />
            </div>
            <button type="submit" className="btn-primary">
              Connect Securely
            </button>
          </form>
          <p className="help-text">Don't have a Pod? <a href="#">Get one here</a>.</p>
        </div>
      ) : (
        <div className="dashboard">
          <header className="dash-header">
            <div className="user-info">
              <div className="avatar"></div>
              <span>{session.info.webId.split('/')[2]}</span>
            </div>
            <button onClick={handleLogout} className="btn-text">Disconnect</button>
          </header>

          <main>
            <div className="status-hero">
              <div className="status-ring active">
                <div className="icon-shield"></div>
              </div>
              <h2>System Secure</h2>
              <p>Your Antigravity link is active and encrypted.</p>
            </div>

            <div className="devices-section">
              <h3>Active Devices</h3>
              <div className="device-list">
                {tunnels.map(t => (
                  <div key={t.id} className="device-card">
                    <div className="device-icon"></div>
                    <div className="device-info">
                      <h4>{t.name}</h4>
                      <span className="ip-badge">{t.ip}</span>
                    </div>
                    <div className="device-status">
                      <span className="dot"></span> {t.status}
                    </div>
                    <button className="btn-revoke" title="Revoke Access">×</button>
                  </div>
                ))}
              </div>
            </div>
          </main>
        </div>
      )}
    </div>
  );
}

export default App;
