/**
 * Captioneer Studio E2E Tests
 * 
 * Tests the complete workflow:
 * - Video upload
 * - Auto-transcription
 * - Caption positioning
 * - Style changes
 * - Export
 */

import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:5174';

test.describe('Captioneer Studio', () => {

    test.beforeEach(async ({ page }) => {
        await page.goto(BASE_URL);
        // Wait for app to load
        await expect(page.locator('text=Captioneer Studio')).toBeVisible();
    });

    test('should display main UI components', async ({ page }) => {
        // Header
        await expect(page.locator('text=Captioneer Studio')).toBeVisible();
        await expect(page.locator('button:has-text("Upload Video")')).toBeVisible();
        await expect(page.locator('button:has-text("Export")')).toBeVisible();

        // Style panel sections
        await expect(page.locator('text=Typography')).toBeVisible();
        await expect(page.locator('text=Colors')).toBeVisible();
        await expect(page.locator('text=Motion')).toBeVisible();
        await expect(page.locator('text=Position')).toBeVisible();

        // Timeline
        await expect(page.locator('[data-testid="timeline"]')).toBeVisible();
    });

    test('should update style controls', async ({ page }) => {
        // Change font size
        const fontSizeSlider = page.locator('input[type="range"]').first();
        await fontSizeSlider.fill('100');

        // Change alignment
        await page.click('button:has-text("right")');

        // Change max words
        await page.click('button:has-text("2")');

        // Verify no errors occurred
        await expect(page.locator('text=Typography')).toBeVisible();
    });

    test('should handle empty state gracefully', async ({ page }) => {
        // Should show empty timeline message
        await expect(page.locator('text=No words yet')).toBeVisible();

        // Export should be disabled
        const exportBtn = page.locator('button:has-text("Export")');
        await expect(exportBtn).toBeDisabled();
    });

    test('should update position when dragging', async ({ page }) => {
        // Get initial position display
        const positionText = page.locator('text=/Position: \\(\\d+, \\d+\\)/');
        await expect(positionText).toBeVisible();

        // Note: Actual drag testing would require Konva-specific handling
        // This test verifies the position display exists
    });

    test('happy path - complete workflow', async ({ page }) => {
        // This test requires a test video file
        // Skip if not in full test environment
        test.skip(true, 'Requires test video file');

        // 1. Upload video
        const fileInput = page.locator('input[type="file"]');
        await fileInput.setInputFiles('./test-assets/sample.mp4');

        // 2. Wait for transcription
        await expect(page.locator('text=Transcribing')).toBeVisible();
        await expect(page.locator('text=Transcribing')).not.toBeVisible({ timeout: 60000 });

        // 3. Verify words appear
        await expect(page.locator('[data-testid="timeline"]')).toContainText('words');

        // 4. Change style
        await page.fill('input[type="range"]', '80'); // Font size

        // 5. Export
        await page.click('button:has-text("Export")');
        await expect(page.locator('text=Exporting')).toBeVisible();
        await expect(page.locator('text=Export Complete')).toBeVisible({ timeout: 120000 });

        // 6. Verify download available
        await expect(page.locator('text=Download Video')).toBeVisible();
    });

});

test.describe('Stress Tests', () => {

    test('should handle rapid style changes', async ({ page }) => {
        await page.goto(BASE_URL);

        // Rapidly change font size
        const slider = page.locator('input[type="range"]').first();

        for (let i = 0; i < 20; i++) {
            await slider.fill(String(50 + i * 5));
            await page.waitForTimeout(50);
        }

        // App should still be responsive
        await expect(page.locator('text=Captioneer Studio')).toBeVisible();
    });

    test('should handle many words', async ({ page }) => {
        await page.goto(BASE_URL);

        // Note: This would require injecting test data via API
        // or using a test video with many words
        test.skip(true, 'Requires test data injection');
    });

});

test.describe('Positioning Tests', () => {

    test('position X/Y inputs should update', async ({ page }) => {
        await page.goto(BASE_URL);

        // Find position inputs
        const xInput = page.locator('input[type="number"]').nth(0);
        const yInput = page.locator('input[type="number"]').nth(1);

        // Change X position
        await xInput.fill('600');
        await expect(xInput).toHaveValue('600');

        // Change Y position  
        await yInput.fill('1200');
        await expect(yInput).toHaveValue('1200');
    });

    test('anchor buttons should toggle', async ({ page }) => {
        await page.goto(BASE_URL);

        // Click center anchor
        await page.click('button:has-text("center")');

        // Click bottom anchor
        await page.click('button:has-text("bottom")');

        // Verify no errors
        await expect(page.locator('text=Position')).toBeVisible();
    });

});
