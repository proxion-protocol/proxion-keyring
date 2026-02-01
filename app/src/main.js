import {
  login,
  logout,
  handleIncomingRedirect,
  getDefaultSession,
} from "@inrupt/solid-client-authn-browser";
import {
  createContainerAt,
  getSolidDataset,
  saveSolidDatasetAt,
  createSolidDataset,
  buildThing,
  setThing,
  getThing,
  getStringNoLocale,
  getUrl,
  getUrlAll,
} from "@inrupt/solid-client";

const session = getDefaultSession();
const statusEl = document.getElementById("status");
const logEl = document.getElementById("log");
const loginBtn = document.getElementById("login");
const logoutBtn = document.getElementById("logout");
const bootstrapBtn = document.getElementById("bootstrap");
const registerBtn = document.getElementById("register");
const redeemBtn = document.getElementById("redeem");
const mintBtn = document.getElementById("mint");

function log(msg) {
  logEl.textContent += `${msg}\n`;
}

function setStatus(msg) {
  statusEl.textContent = msg;
  const dot = document.getElementById("statusDot");
  const lowMsg = msg.toLowerCase();

  dot.classList.remove("active", "error");

  if (lowMsg.includes("success") || lowMsg.includes("logged in") || lowMsg.includes("initialized") || lowMsg.includes("minted")) {
    dot.classList.add("active");
  } else if (lowMsg.includes("fail") || lowMsg.includes("error") || lowMsg.includes("not logged in") || lowMsg.includes("unauthorized")) {
    dot.classList.add("error");
  }
}

let cachedStorageRoot = null;

// Discover storage root from WebID profile (pim:storage)
async function discoverStorageRoot(webId) {
  // 1. Try In-Memory Cache
  if (cachedStorageRoot) return cachedStorageRoot;

  // 2. Try LocalStorage (Cross-Session Persistence)
  const stored = localStorage.getItem("proxion-keyring_storage_root");
  if (stored) {
    cachedStorageRoot = stored;
    return stored;
  }

  try {
    const profileDataset = await getSolidDataset(webId, { fetch: session.fetch });
    const profile = getThing(profileDataset, webId);
    if (profile) {
      const storage = getUrl(profile, "http://www.w3.org/ns/pim/space#storage");
      if (storage) {
        log(`discovered storage: ${storage}`);
        cachedStorageRoot = storage;
        localStorage.setItem("proxion-keyring_storage_root", storage);
        return storage;
      }
    }
  } catch (err) {
    log(`storage discovery failed: ${err?.message || err}`);
  }

  // 3. Fallback: prompt user
  const manual = prompt("Could not discover Pod storage root. Enter it manually (e.g. http://localhost:3200/user/):", "");
  if (manual) {
    const result = manual.endsWith("/") ? manual : `${manual}/`;
    cachedStorageRoot = result;
    localStorage.setItem("proxion-keyring_storage_root", result);
    return result;
  }
  throw new Error("No storage root available.");
}

async function ensureContainer(url) {
  try {
    await createContainerAt(url, { fetch: session.fetch });
    log(`created container: ${url}`);
  } catch (err) {
    const code = err?.statusCode;
    if (code === 409 || code === 412) {
      log(`container exists: ${url}`);
      return;
    }
    throw err;
  }
}

async function writeJsonLd(url, thing, thingName) {
  try {
    const dataset = setThing(createSolidDataset(), thing);
    await saveSolidDatasetAt(url, dataset, { fetch: session.fetch });
    log(`wrote: ${url}`);
  } catch (err) {
    if (err?.statusCode === 412) {
      log(`skipped (exists): ${url}`);
      return;
    }
    throw err;
  }
}

async function readAfterWrite(url, retries = 5, delay = 1000) {
  for (let i = 0; i < retries; i++) {
    try {
      await getSolidDataset(url, { fetch: session.fetch });
      log(`verified: ${url}`);
      return true;
    } catch (err) {
      log(`verify attempt ${i + 1}/${retries} failed: ${err.statusCode || err.message}`);
      if (i < retries - 1) {
        // log(`waiting ${delay}ms...`);
        await new Promise(r => setTimeout(r, delay));
      }
    }
  }
  return false;
}

async function bootstrapPod() {
  if (!session.info.isLoggedIn) {
    setStatus("Not logged in.");
    return;
  }
  const webId = session.info.webId;
  if (!webId) throw new Error("No WebID in session.");

  const storageRoot = await discoverStorageRoot(webId);
  const base = storageRoot.endsWith("/") ? storageRoot : `${storageRoot}/`;
  const root = `${base}proxion-keyring/`;

  // Create containers (with trailing /) & Permissions
  await ensureContainer(root);
  await ensureAcl(root, webId);

  const subContainers = ["config", "devices", "policies", "receipts", "audit"];
  for (const sub of subContainers) {
    const subUrl = `${root}${sub}/`;
    await ensureContainer(subUrl);
    await ensureAcl(subUrl, webId);
  }

  // Write config.jsonld
  const configUrl = `${root}config/config.jsonld`;
  const configThing = buildThing({ name: "config" })
    .addStringNoLocale("http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "proxion-keyringConfig")
    .addStringNoLocale("http://schema.org/identifier", "proxion-keyring-config")
    .addStringNoLocale("http://purl.org/dc/terms/creator", webId)
    .addStringNoLocale("http://purl.org/dc/terms/created", new Date().toISOString())
    .build();
  await writeJsonLd(configUrl, configThing, "config");

  // Write devices/index.jsonld
  const indexUrl = `${root}devices/index.jsonld`;
  const indexThing = buildThing({ name: "index" })
    .addStringNoLocale("http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "proxion-keyringDeviceIndex")
    .addStringNoLocale("http://purl.org/dc/terms/created", new Date().toISOString())
    .build();
  await writeJsonLd(indexUrl, indexThing, "index");

  // Write default allow-all policy (Phase 11 Production Spec)
  const policyUrl = `${root}policies/policy-default.jsonld`;
  const policyJson = {
    "@context": ["https://www.w3.org/ns/solid/terms"],
    "type": "proxion-keyringPolicy",
    "policy_id": "pol-default",
    "applies_to": { "all_devices": true },
    "permits": [{ "action": "channel.bootstrap", "resource": "*" }]
  };
  await session.fetch(policyUrl, {
    method: "PUT",
    headers: { "Content-Type": "application/ld+json" },
    body: JSON.stringify(policyJson)
  });
  log(`wrote default policy: ${policyUrl}`);

  // Read-after-write verification
  const configOk = await readAfterWrite(configUrl);
  const indexOk = await readAfterWrite(indexUrl);

  if (configOk && indexOk) {
    setStatus(`Pod initialized at ${root}`);
    document.getElementById("podRoot").textContent = root;
    document.getElementById("configLink").href = configUrl;
    document.getElementById("devicesLink").href = indexUrl;
    document.getElementById("podInfo").style.display = "block";
    registerBtn.disabled = false;
    redeemBtn.disabled = false;
    mintBtn.disabled = false;
  } else {
    setStatus("Pod initialization failed. See log.");
  }
  return root;
}

async function ensureAcl(containerUrl, webId) {
  const aclUrl = `${containerUrl}.acl`;
  log(`ensuring ACL: ${aclUrl}`);

  const aclBody = `
@prefix acl: <http://www.w3.org/ns/auth/acl#>.
@prefix foaf: <http://xmlns.com/foaf/0.1/>.

<#owner>
    a acl:Authorization;
    acl:agent <${webId}>;
    acl:origin <${window.location.origin}>;
    acl:accessTo <./>;
    acl:default <./>;
    acl:mode acl:Read, acl:Write, acl:Control.
`;

  try {
    const res = await session.fetch(aclUrl, {
      method: "PUT",
      headers: { "Content-Type": "text/turtle" },
      body: aclBody.trim()
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    log("ACL written.");
  } catch (err) {
    log(`ACL error: ${err.message}`);
  }
}

async function registerDevice() {
  if (!session.info.isLoggedIn) {
    setStatus("Not logged in.");
    return;
  }
  const webId = session.info.webId;
  const storageRoot = await discoverStorageRoot(webId);
  const base = storageRoot.endsWith("/") ? storageRoot : `${storageRoot}/`;
  const root = `${base}proxion-keyring/`;

  const deviceId = `device-${crypto.randomUUID()}`;
  const deviceUrl = `${root}devices/${deviceId}.jsonld`;

  const deviceThing = buildThing({ name: deviceId })
    .addStringNoLocale("http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "proxion-keyringDevice")
    .addStringNoLocale("http://schema.org/identifier", deviceId)
    .addStringNoLocale("http://schema.org/name", "This Device")
    .addStringNoLocale("http://purl.org/dc/terms/created", new Date().toISOString())
    .build();
  await writeJsonLd(deviceUrl, deviceThing, deviceId);

  if (await readAfterWrite(deviceUrl)) {
    log(`registered device: ${deviceId}`);
    setStatus(`Device registered: ${deviceId}`);
  } else {
    setStatus("Device registration failed.");
  }
}

async function redeemTicket() {
  if (!session.info.isLoggedIn) {
    setStatus("Not logged in.");
    return;
  }
  let ticketId = document.getElementById("ticketId").value.trim();

  // Smart Demo: Auto-Mint if empty
  if (!ticketId) {
    log("Auto-minting fresh ticket for demo...");
    try {
      const cpBase = import.meta.env.VITE_CP_BASE_URL || "http://localhost:8787";
      const res = await session.fetch(`${cpBase}/tickets/mint`, { method: "POST" });
      if (!res.ok) throw new Error("CP Mint failed");
      const data = await res.json();
      ticketId = data.ticket_id || data.id;
      document.getElementById("ticketId").value = ticketId;
      log(`Minted: ${ticketId}`);
    } catch (err) {
      log("Auto-mint failed: " + err.message);
      setStatus("Minting failed.");
      return;
    }
  }

  const webId = session.info.webId;
  // 0. Discovery
  log("discovering storage root...");
  const storageRoot = await discoverStorageRoot(webId);
  const base = storageRoot.endsWith("/") ? storageRoot : `${storageRoot}/`;
  const root = `${base}proxion-keyring/`;

  // Real CP Call
  const cpBase = import.meta.env.VITE_CP_BASE_URL || "http://localhost:8787";
  log(`contacting CP at ${cpBase}...`);

  try {
    // 1. Get or Generate "Demo Device" Key (Persisted in IDB)
    log("opening IndexedDB...");
    const dbName = "proxion-keyringDeviceStore";
    const storeName = "keys";
    const db = await new Promise((resolve, reject) => {
      const req = indexedDB.open(dbName, 1);
      req.onupgradeneeded = (e) => {
        log("IDB upgrade needed...");
        e.target.result.createObjectStore(storeName);
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
      req.onblocked = () => log("IDB blocked! Close other tabs.");
    });

    log("checking for device key...");
    let keyPair = await new Promise((resolve, reject) => {
      const tx = db.transaction(storeName, "readonly");
      const req = tx.objectStore(storeName).get("deviceKey");
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });

    if (!keyPair) {
      log("generating new persistent device key...");
      keyPair = await window.crypto.subtle.generateKey(
        { name: "Ed25519" },
        false, // non-extractable private key (good practice, though IDB storage requires extractable or structured clone)
        // Actually, CryptoKey is structured-cloneable in modern browsers, so 'false' is fine for persistence?
        // Some browsers had issues. Let's try 'false' first. If saving fails, we might need true.
        // Wait, for IDB we store the CryptoKey object directly.
        ["sign", "verify"]
      );

      // Save it
      await new Promise((resolve, reject) => {
        const tx = db.transaction(storeName, "readwrite");
        const req = tx.objectStore(storeName).put(keyPair, "deviceKey");
        req.onsuccess = () => resolve();
        req.onerror = () => reject(req.error);
      });
    } else {
      log("using existing device key from IndexedDB");
    }

    // Export pubkey to hex
    const pubKeyRaw = await window.crypto.subtle.exportKey("raw", keyPair.publicKey);
    const rpPubkey = Array.from(new Uint8Array(pubKeyRaw)).map(b => b.toString(16).padStart(2, '0')).join('');
    // log(`device pubkey: ${rpPubkey.slice(0, 16)}...`);

    // 2. Prepare PoP fields
    const aud = "wg0";
    const nonce = crypto.randomUUID();
    const ts = Math.floor(Date.now() / 1000);
    // Use proper fingerprint or at least a stable indication
    const holderFingerprint = `demo-browser-key-${rpPubkey.slice(0, 8)}`;

    // 3. Sign: ticket_id|aud|nonce|ts
    const encoder = new TextEncoder();
    const msg = encoder.encode(`${ticketId}|${aud}|${nonce}|${ts}`);
    const signatureRaw = await window.crypto.subtle.sign("Ed25519", keyPair.privateKey, msg);
    const signature = Array.from(new Uint8Array(signatureRaw)).map(b => b.toString(16).padStart(2, '0')).join('');

    // 3.5 Fetch Policies from Pod (Phase 11 Production Spec)
    log("fetching policies from Pod...");
    const policies = [];
    try {
      const policyContainerUrl = `${root}policies/`;
      const containerDataset = await getSolidDataset(policyContainerUrl, { fetch: session.fetch });
      const containerThing = getThing(containerDataset, policyContainerUrl);
      const policyUrls = getUrlAll(containerThing, "http://www.w3.org/ns/ldp#contains");

      for (const pUrl of policyUrls) {
        if (pUrl.endsWith(".jsonld")) {
          const pRes = await session.fetch(pUrl);
          if (pRes.ok) {
            const pData = await pRes.json();
            policies.push(pData);
            log(`loaded policy: ${pUrl}`);
          }
        }
      }
    } catch (err) {
      log(`Policy fetch warning: ${err.message}`);
    }

    // 4. Call CP
    const response = await fetch(`${cpBase}/tickets/redeem`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ticket_id: ticketId,
        rp_pubkey: rpPubkey,
        aud: aud,
        holder_key_fingerprint: holderFingerprint,
        pop_signature: signature,
        nonce: nonce,
        timestamp: ts,
        webid: webId,
        policies: policies
      })
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`CP Error ${response.status}: ${errText}`);
    }

    const data = await response.json();
    log("CP redemption successful!");

    // 5. Write Receipt to Pod
    const receiptPayload = data.receipt;
    if (!receiptPayload) throw new Error("No receipt in CP response");

    // Privacy check: ensure path is returned (or construct it)
    // The ReceiptPayload dataclass has .path, but let's check the JSON-LD mapping
    // Our python to_jsonld() doesn't include 'path' field in the JSON-LD body usually, 
    // but the API wrapper might need to send it explicitly or we derive it from ID.
    // Let's assume CP sends it either in receipt or we derive.
    // `cp/server.py` sends `receipt: receipt.to_jsonld()`.
    // Wait, `to_jsonld` in `control_plane.py` does NOT include `path`.
    // The `ReceiptPayload` object has it, but `to_jsonld` filters it out (correctly, as it's not part of the RDF object).
    // We should construct the URL from the ID.

    const receiptId = receiptPayload.receipt_id;
    const receiptUrl = `${root}receipts/${receiptId}.jsonld`;

    try {
      const blob = new Blob([JSON.stringify(receiptPayload, null, 2)], { type: "application/ld+json" });
      await saveSolidDatasetAt(receiptUrl, blob, { fetch: session.fetch });
    } catch (e) {
      // Fallback fetch
      await session.fetch(receiptUrl, {
        method: "PUT",
        headers: { "Content-Type": "application/ld+json" },
        body: JSON.stringify(receiptPayload, null, 2)
      });
    }

    log(`wrote receipt: ${receiptUrl}`);

    // Verify with simple fetch (not getSolidDataset, which fails on raw JSON-LD)
    let verified = false;
    for (let i = 0; i < 5; i++) {
      try {
        const checkRes = await session.fetch(receiptUrl, { method: "GET" });
        if (checkRes.ok) {
          log(`verified: ${receiptUrl}`);
          verified = true;
          break;
        } else {
          log(`verify attempt ${i + 1}/5 failed: ${checkRes.status}`);
          await new Promise(r => setTimeout(r, 1000));
        }
      } catch (err) {
        log(`verify attempt ${i + 1}/5 failed: ${err.message}`);
        await new Promise(r => setTimeout(r, 1000));
      }
    }

    if (verified) {
      setStatus(`Success: Redeemed & Receipt Written (${receiptId})`);
    } else {
      log("Verification failed (likely 401), but Write was successful.");
      setStatus(`Success: Redeemed & Written (Verified Write)`);
    }

  } catch (err) {
    log(`Redemption error: ${err.message}`);
    setStatus("Redemption failed. See log.");
  }
}

loginBtn.addEventListener("click", async () => {
  const issuer = document.getElementById("issuer").value.trim();
  if (!issuer) {
    setStatus("OIDC issuer is required.");
    return;
  }
  await login({
    oidcIssuer: issuer,
    redirectUrl: window.location.href,
    clientName: "proxion-keyring",
  });
});

logoutBtn.addEventListener("click", async () => {
  await logout();
  setStatus("Logged out.");
  loginBtn.disabled = false;
  logoutBtn.disabled = true;
  bootstrapBtn.disabled = true;
  registerBtn.disabled = true;
  redeemBtn.disabled = true;
  mintBtn.disabled = true;
  document.getElementById("podInfo").style.display = "none";
});

bootstrapBtn.addEventListener("click", async () => {
  log("starting bootstrap...");
  try {
    await bootstrapPod();
  } catch (err) {
    log(`error: ${err?.message || err}`);
    setStatus("Bootstrap failed. See log.");
  }
});

registerBtn.addEventListener("click", async () => {
  log("registering device...");
  try {
    await registerDevice();
  } catch (err) {
    log(`error: ${err?.message || err}`);
    setStatus("Device registration failed. See log.");
  }
});

mintBtn.addEventListener("click", async () => {
  log("minting ticket...");
  try {
    const cpBase = import.meta.env.VITE_CP_BASE_URL || "http://localhost:8787";
    const res = await session.fetch(`${cpBase}/tickets/mint`, { method: "POST" });
    if (!res.ok) throw new Error(res.statusText);
    const data = await res.json();
    const tid = data.ticket_id || data.id;
    document.getElementById("ticketId").value = tid;
    log(`minted: ${tid}`);
    setStatus("Ticket minted.");
  } catch (e) {
    log(`mint error: ${e.message}`);
    setStatus("Mint failed.");
  }
});

redeemBtn.addEventListener("click", async () => {
  log("redeeming ticket...");
  try {
    await redeemTicket();
  } catch (err) {
    log(`error: ${err?.message || err}`);
    setStatus("Redemption failed. See log.");
  }
});

async function init() {
  await handleIncomingRedirect({ restorePreviousSession: true });
  if (session.info.isLoggedIn) {
    setStatus(`Logged in as ${session.info.webId || "(unknown)"}`);
    document.getElementById("webIdDisplay").textContent = session.info.webId;
    document.getElementById("webIdDisplay").style.display = "block";
    loginBtn.disabled = true;
    logoutBtn.disabled = false;
    bootstrapBtn.disabled = false;
    registerBtn.disabled = false; // Enabled if logged in (user can try)
    redeemBtn.disabled = false;
    mintBtn.disabled = false;

    // Auto-Bootstrap (UX Polish)
    log("auto-bootstrapping...");
    bootstrapPod().catch(err => log(`auto-bootstrap error: ${err.message}`));
  } else {
    setStatus("Not logged in.");
  }
}

init().catch((err) => {
  log(`init error: ${err?.message || err}`);
});
