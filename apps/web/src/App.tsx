import { lazy, Suspense } from 'react';
import MLBGame from './mlb/game/MLBGame';
const DeveloperHarness = lazy(() => import('./DeveloperHarness'));
export default function App() {
  return location.pathname.replace(/\/$/, '') === '/dev' ? (
    <Suspense fallback={<p role="status">Loading diagnostics…</p>}>
      <DeveloperHarness />
    </Suspense>
  ) : (
    <MLBGame />
  );
}
