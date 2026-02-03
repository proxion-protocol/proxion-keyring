import { _electron as electron } from '@playwright/test';
import { test, expect } from '@playwright/test';
import { fileURLToPath } from 'url';
import path from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test.describe('Calibre-Web SSO Verification', () => {
    let electronApp;
    let firstWindow;

    test.beforeAll(async () => {
        electronApp = await electron.launch({
            args: [path.join(__dirname, '../electron/main.js')],
            env: { ...process.env, NODE_ENV: 'development' },
        });

        firstWindow = await electronApp.firstWindow();
    });

    test.afterAll(async () => {
        await electronApp.close();
    });

    test('Navigate to Calibre-Web and check for auto-fill', async () => {
        firstWindow.on('console', msg => console.log('PAGE LOG:', msg.text()));

        // 1. Handle Wizard if present
        const wizardBtn = firstWindow.locator('button:has-text("Get Started")');
        if (await wizardBtn.isVisible()) {
            await wizardBtn.click();
            console.log('Wizard dismissed.');
        }

        // 2. Open Library tab
        await firstWindow.click('button:has-text("App Library")');

        // 3. Find Calibre-Web and click "Open UI"
        // Assuming Calibre-Web is already installed as per previous turns
        const calibreBtn = firstWindow.locator('.app-card-modern:has-text("Calibre-Web")').locator('button:has-text("Open UI")');
        await calibreBtn.click();

        // 4. Wait for the webview tab to become active
        await firstWindow.waitForSelector('.webview-container:visible webview', { timeout: 15000 });

        console.log('Calibre-Web tab opened. Waiting for injection...');

        // 5. Wait for the injection heartbeat (green border)
        // We check this by evaluating inside the main window since it's a DOM style applied to the webview container or body
        // Wait, the border is applied inside the webview's body.

        // To check inside the webview, we need to use capture the webview's internal page
        // Playwright doesn't easily expose 'webview' inner pages, so we use evaluation on the webview element

        const diag = await firstWindow.evaluate(async () => {
            const webview = document.querySelector('webview');
            if (!webview) return { error: 'no webview' };

            try {
                // Wait up to 5s for fill to complete inside webview
                for (let i = 0; i < 10; i++) {
                    const user = await webview.executeJavaScript('document.querySelector("#username")?.value');
                    if (user === 'admin') break;
                    await new Promise(r => setTimeout(r, 500));
                }

                const isActive = await webview.executeJavaScript('window.PROXION_SSO_ACTIVE');
                const userValue = await webview.executeJavaScript('document.querySelector("#username")?.value');
                const border = await webview.executeJavaScript('document.body.style.borderTop');
                const logs = await webview.executeJavaScript('window.PROXION_LOGS');
                return { isActive, userValue, border, logs };
            } catch (e) {
                return { error: e.message };
            }
        });

        console.log('Diagnostic State:', JSON.stringify(diag, null, 2));
        if (diag.logs) {
            console.log('--- Webview Logs ---');
            diag.logs.forEach(l => console.log(l));
            console.log('-------------------');
        }

        expect(diag.error).toBeUndefined();
        expect(diag.isActive).toBe(true);
        expect(diag.userValue).toBe('admin');

        // Extra wait for visual confirmation in screenshot
        await new Promise(r => setTimeout(r, 2000));

        // Take a screenshot of the webview area
        await firstWindow.screenshot({ path: path.join(__dirname, 'calibre_sso_final.png') });
        console.log('Final screenshot captured: calibre_sso_final.png');
    });
});
