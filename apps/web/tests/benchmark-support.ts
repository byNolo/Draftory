import type { Browser } from '@playwright/test';

export function distribution(values: number[]) {
  const sorted = [...values].sort((a, b) => a - b);
  const n = sorted.length;
  const mean = values.reduce((a, b) => a + b, 0) / n;
  return {
    n,
    median:
      n % 2 ? sorted[(n - 1) / 2] : (sorted[n / 2 - 1] + sorted[n / 2]) / 2,
    min: sorted[0],
    max: sorted[n - 1],
    sd: Math.sqrt(
      values.reduce((sum, value) => sum + (value - mean) ** 2, 0) /
        Math.max(1, n - 1),
    ),
  };
}

// Worker JS heap only. Neither this nor linear memory is process RSS; no GC is forced.
export async function workerHeap(browser: Browser) {
  if (browser.browserType().name() !== 'chromium')
    return {
      unavailable:
        'Worker JS heap snapshots require Chromium CDP; WASM capacity is reported on all engines.',
    };
  const connection = await browser.newBrowserCDPSession();
  try {
    const targets = await connection.send('Target.getTargets');
    const target = targets.targetInfos.find(
      (entry) =>
        entry.type === 'worker' && entry.url.includes('season.worker-'),
    );
    if (!target) return { unavailable: 'No worker target available.' };
    const { sessionId } = await connection.send('Target.attachToTarget', {
      targetId: target.targetId,
      flatten: false,
    });
    const usage = await new Promise<unknown>((resolve, reject) => {
      const timer = setTimeout(
        () => reject(new Error('Worker heap snapshot timed out')),
        5000,
      );
      connection.on('Target.receivedMessageFromTarget', (event) => {
        if (event.sessionId !== sessionId) return;
        const message = JSON.parse(event.message);
        if (message.id !== 1) return;
        clearTimeout(timer);
        if (message.error) reject(new Error(JSON.stringify(message.error)));
        else resolve(message.result);
      });
      void connection
        .send('Target.sendMessageToTarget', {
          sessionId,
          message: JSON.stringify({ id: 1, method: 'Runtime.getHeapUsage' }),
        })
        .catch((error) => {
          clearTimeout(timer);
          reject(error);
        });
    });
    await connection.send('Target.detachFromTarget', { sessionId });
    return { usage };
  } catch (error) {
    return { unavailable: String(error) };
  } finally {
    await connection.detach();
  }
}
