import {
  login,
  logout,
  handleIncomingRedirect,
  getDefaultSession,
} from "@inrupt/solid-client-authn-browser";
import {
  createContainerAt,
  createSolidDataset,
  saveSolidDatasetAt,
  buildThing,
  setThing,
  getPodUrlAll,
} from "@inrupt/solid-client";

const session = getDefaultSession();
const statusEl = document.getElementById("status");
const logEl = document.getElementById("log");
const loginBtn = document.getElementById("login");
const logoutBtn = document.getElementById("logout");
const bootstrapBtn = document.getElementById("bootstrap");

function log(msg) {
  logEl.textContent += `${msg}\n`;
}

function setStatus(msg) {
  statusEl.textContent = msg;
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

async function writeConfig(configUrl, webId) {
  const dataset = createSolidDataset();
  const thing = buildThing({ name: "config" })
    .addStringNoLocale("http://www.w3.org/1999/02/22-rdf-syntax-ns#type", "KleitikonConfig")
    .addStringNoLocale("http://schema.org/identifier", "kleitikon-config")
    .addStringNoLocale("http://purl.org/dc/terms/creator", webId || "")
    .addStringNoLocale("http://purl.org/dc/terms/created", new Date().toISOString())
    .build();
  const updated = setThing(dataset, thing);
  await saveSolidDatasetAt(configUrl, updated, { fetch: session.fetch });
  log(`wrote config: ${configUrl}`);
}

async function bootstrapPod() {
  if (!session.info.isLoggedIn) {
    setStatus("Not logged in.");
    return;
  }
  const webId = session.info.webId;
  if (!webId) {
    throw new Error("No WebID in session.");
  }
  const pods = await getPodUrlAll(webId, { fetch: session.fetch });
  if (!pods || pods.length === 0) {
    throw new Error("No Pod URL found for WebID.");
  }
  const podRoot = pods[0];
  const base = podRoot.endsWith("/") ? podRoot : `${podRoot}/`;
  const root = `${base}kleitikon/`;

  await ensureContainer(root);
  await ensureContainer(`${root}policies/`);
  await ensureContainer(`${root}receipts/`);
  await ensureContainer(`${root}audit/`);
  await ensureContainer(`${root}devices/`);
  await ensureContainer(`${root}config/`);

  await writeConfig(`${root}config/config.jsonld`, webId);
  setStatus(`Bootstrapped at ${root}`);
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
    clientName: "Kleitikon",
  });
});

logoutBtn.addEventListener("click", async () => {
  await logout();
  setStatus("Logged out.");
  loginBtn.disabled = false;
  logoutBtn.disabled = true;
  bootstrapBtn.disabled = true;
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

async function init() {
  await handleIncomingRedirect({ restorePreviousSession: true });
  if (session.info.isLoggedIn) {
    setStatus(`Logged in as ${session.info.webId || "(unknown)"}`);
    loginBtn.disabled = true;
    logoutBtn.disabled = false;
    bootstrapBtn.disabled = false;
  } else {
    setStatus("Not logged in.");
  }
}

init().catch((err) => {
  log(`init error: ${err?.message || err}`);
});
