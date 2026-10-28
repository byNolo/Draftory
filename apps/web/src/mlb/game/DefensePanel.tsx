import { useEffect, useState } from 'react';
import type { DraftEngine, DraftState } from '../draft/engine';
import {
  fieldingAssignments,
  loadDefense,
  type DefenseProfile,
} from '../defense';

export default function DefensePanel({
  engine,
  draft,
  enabled,
  disabled,
  onChange,
}: {
  engine: DraftEngine;
  draft: DraftState;
  enabled: boolean;
  disabled: boolean;
  onChange: (enabled: boolean) => void;
}) {
  const [profiles, setProfiles] = useState<DefenseProfile[]>([]);
  const [error, setError] = useState('');
  useEffect(() => {
    if (!enabled) return;
    let active = true;
    loadDefense()
      .then((s) => {
        const rows = fieldingAssignments(engine, draft, s);
        if (active) {
          setProfiles(rows);
          setError('');
        }
      })
      .catch((e: unknown) => {
        if (active) setError(String(e));
      });
    return () => {
      active = false;
    };
  }, [engine, draft, enabled]);
  return (
    <section className="rules" aria-label="Error avoidance">
      <label className="defense-toggle">
        <input
          type="checkbox"
          checked={enabled}
          disabled={disabled}
          onChange={(e) => onChange(e.target.checked)}
        />{' '}
        Experimental error avoidance
      </label>
      <p>
        {enabled
          ? 'Your first baseman, second baseman, third baseman and shortstop can change supported error reaches while the opponent bats. Catcher, outfield and DH effects remain neutral.'
          : 'Neutral defense: the original simulation, available for comparison.'}
      </p>
      <p>
        Models recorded error avoidance only. Range, arms, catcher specialties
        and double-play skill remain neutral.
      </p>
      {enabled && error && (
        <p role="alert">{error} Turn this option off to use neutral defense.</p>
      )}
      {enabled && !error && (
        <details>
          <summary>Fielding samples and estimates</summary>
          <ul>
            {profiles.map((p) => (
              <li key={p.position}>
                {p.position}: {engine.player(p.playerId).name} ·{' '}
                {p.innOuts === null
                  ? 'Unknown innings'
                  : `${(p.innOuts / 3).toFixed(1)} defensive innings`}
                {' · '}
                {p.chances ?? 'Unknown'} chances ·{' '}
                {p.status === 'observed'
                  ? `estimated error rate ${(p.errorRatio / 10000).toFixed(0)}% of position reference`
                  : p.status === 'modelNeutral'
                    ? 'event mapping unavailable — neutral effect'
                    : `${p.status} sample — neutral effect`}
              </li>
            ))}
          </ul>
          <p>
            100% is the position reference, not a defensive grade. Estimates are
            strongly smoothed; fewer recorded errors do not prove better range.
          </p>
        </details>
      )}
    </section>
  );
}
