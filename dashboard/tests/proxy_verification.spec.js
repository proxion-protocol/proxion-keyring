import { _electron as electron } from '@playwright/test';
import { test, expect } from '@playwright/test';
import { fileURLToPath } from 'url';
import path from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test('Header Injection Verification', async () => {
    const electronApp = await electron.launch({
        args: [path.join(__dirname, '../electron/main.js')],
        env: { ...process.env, NODE_ENV: 'development' },
    });

    const window = await electronApp.firstWindow();

    // 1. Sync session context
    const testWebId = "https://proxion.protocol/users/test-user";
    const testToken = "proxion_capability_token_12345";

    console.log("Setting session context...");
    await window.evaluate(({ webId, token }) => {
        window.electronAPI.setSessionContext(webId, token);
    }, { webId: testWebId, token: testToken });

    // Give it a moment to sync in main
    await new Promise(r => setTimeout(r, 500));

    // 2. Perform fetch to managed port 9999
    console.log("Performing fetch to mock service on port 9999...");
    const result = await window.evaluate(async () => {
        const resp = await fetch('http://127.0.0.1:9999/test');
        return await resp.json();
    });

    console.log("Received Headers from Mock Service:", JSON.stringify(result.received_headers, null, 2));

    // 3. Verify headers
    expect(result.received_headers['Authorization']).toBe(`Bearer ${testToken}`);
    expect(result.received_headers['X-Proxion-Webid']).toBe(testWebId);

    console.log("Verification SUCCESS: Headers injected correctly!");

    await electronApp.close();
});
