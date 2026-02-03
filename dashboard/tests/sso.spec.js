import { _electron as electron } from '@playwright/test';
import { test, expect } from '@playwright/test';
import { fileURLToPath } from 'url';
import path from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test.describe('Proxion Sovereign SSO Integration', () => {
    let electronApp;
    let firstWindow;

    test.beforeAll(async () => {
        electronApp = await electron.launch({
            args: [path.join(__dirname, '../electron/main.js')],
            env: { ...process.env, NODE_ENV: 'development' },
        });

        firstWindow = await electronApp.firstWindow();
        firstWindow.on('console', msg => console.log(`[ELECTRON CONSOLE]: ${msg.text()}`));
        firstWindow.on('pageerror', err => console.error(`[ELECTRON ERROR]: ${err.message}`));
    });

    test.afterAll(async () => {
        await electronApp.close();
    });

    test('Dashboard loads and shows UI', async () => {
        await firstWindow.waitForFunction(() => {
            return document.querySelector('.app-container') || document.querySelector('.login-card');
        }, { timeout: 30000 });

        await firstWindow.screenshot({ path: path.join(__dirname, 'dashboard_load.png') });
        console.log('Screenshot saved to dashboard_load.png');

        const bodyText = await firstWindow.innerText('body');
        expect(bodyText).not.toBe('');
    });

    test('IPC getRepoRoot is functional in Renderer', async () => {
        // Wait for the API to be exposed
        await firstWindow.waitForFunction(() => window.electronAPI && typeof window.electronAPI.getRepoRoot === 'function', { timeout: 10000 });

        const repoRoot = await firstWindow.evaluate(async () => {
            try {
                return await window.electronAPI.getRepoRoot();
            } catch (e) {
                return `ERROR: ${e.message}`;
            }
        });

        console.log(`Verified Repo Root: ${repoRoot}`);
        expect(repoRoot).not.toBeNull();
        expect(repoRoot).not.toContain('ERROR');
    });
});
