import { useRef, useState, type PointerEvent } from 'react';
import type { DraftEngine, DraftState } from '../draft/engine';
import { rate, type HistoricalBatting } from './batting';
import {
  defaultBattingOrder,
  moveBatter,
  type BattingOrder,
} from '../draft/batting-order';

export default function BattingOrderEditor({
  engine,
  draft,
  order,
  stats,
  disabled,
  onChange,
}: {
  engine: DraftEngine;
  draft: DraftState;
  order: BattingOrder;
  stats: Record<string, HistoricalBatting>;
  disabled: boolean;
  onChange: (order: BattingOrder, announcement: string) => void;
}) {
  const [dragging, setDragging] = useState<string>();
  const [target, setTarget] = useState<string>();
  const list = useRef<HTMLOListElement>(null);
  function move(id: string, destination: number) {
    if (disabled) return;
    onChange(
      moveBatter(order, id, destination),
      `${engine.player(id).name} now bats ${destination + 1}.`,
    );
  }
  function hit(event: PointerEvent<HTMLButtonElement>) {
    const row = document
      .elementFromPoint(event.clientX, event.clientY)
      ?.closest<HTMLElement>('[data-batting-player]');
    return row && list.current?.contains(row)
      ? row.dataset.battingPlayer
      : undefined;
  }
  return (
    <section className="batting-editor" aria-labelledby="batting-order-title">
      <div className="batting-heading">
        <div>
          <p className="eyebrow">Build your lineup</p>
          <h2 id="batting-order-title">Batting order</h2>
        </div>
        <span className="batting-season">
          {engine.catalog.year} historical stats
        </span>
      </div>
      <p className="batting-insight">
        Compare on-base ability and power as you arrange your nine hitters.
      </p>
      <p id="batting-order-help" className="muted">
        Drag a handle or use Move up and Move down. A focused handle also
        accepts Arrow Up/Down. Fielding positions stay assigned.
      </p>
      <ol ref={list} aria-label="Batting order" className="batting-order">
        {order.map((id, i) => {
          const player = engine.player(id);
          const pick = draft.history.find((p) => p.playerId === id)!;
          const s = stats[id];
          const metrics = [
            ['AVG', 'Batting average', rate(s?.avg ?? null)],
            ['OBP', 'On-base percentage', rate(s?.obp ?? null)],
            ['SLG', 'Slugging percentage', rate(s?.slg ?? null)],
            [
              'OPS',
              'On-base plus slugging',
              rate(
                s && s.obp !== null && s.slg !== null ? s.obp + s.slg : null,
              ),
            ],
            ['HR', 'Home runs', s?.hr ?? '—'],
            ['SB', 'Stolen bases', s?.sb ?? '—'],
            [
              'SB%',
              `Stolen-base success rate${s && s.sb !== null && s.cs !== null ? `: ${s.sb} stolen, ${s.cs} caught stealing` : ''}`,
              s?.sbPct == null ? '—' : `${(s.sbPct * 100).toFixed(1)}%`,
            ],
            ['PA', 'Plate appearances', s?.pa ?? '—'],
          ];
          return (
            <li
              key={id}
              data-batting-player={id}
              className={target === id ? 'drop-target' : ''}
            >
              <span className="batting-number" aria-label={`Bats ${i + 1}`}>
                {i + 1}
              </span>
              <span className="batting-name">
                <strong>{player.name}</strong>
                <small>
                  <span className="batting-position">{pick.position}</span>{' '}
                  {s?.teams.join(' / ')}
                </small>
              </span>
              <dl
                className="batting-stats"
                aria-label={`${player.name} historical batting statistics`}
              >
                {metrics.map(([label, description, value]) => (
                  <div
                    key={label}
                    className={label === 'OPS' ? 'batting-ops' : undefined}
                  >
                    <dt>
                      <abbr title={String(description)}>{label}</abbr>
                    </dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
              <div className="batting-controls">
                <button
                  type="button"
                  disabled={disabled || i === 0}
                  aria-label={`Move ${player.name} up`}
                  onClick={() => move(id, i - 1)}
                >
                  ↑
                </button>
                <button
                  type="button"
                  disabled={disabled || i === 8}
                  aria-label={`Move ${player.name} down`}
                  onClick={() => move(id, i + 1)}
                >
                  ↓
                </button>
                <button
                  type="button"
                  className="drag-handle"
                  disabled={disabled}
                  aria-label={`Reorder ${player.name}`}
                  aria-describedby="batting-order-help"
                  onKeyDown={(event) => {
                    if (
                      (event.key === 'ArrowUp' && i > 0) ||
                      (event.key === 'ArrowDown' && i < 8)
                    ) {
                      event.preventDefault();
                      move(id, i + (event.key === 'ArrowUp' ? -1 : 1));
                    }
                  }}
                  onPointerDown={(event) => {
                    if (disabled || event.button !== 0) return;
                    event.currentTarget.focus();
                    event.currentTarget.setPointerCapture(event.pointerId);
                    setDragging(id);
                    setTarget(id);
                  }}
                  onPointerMove={(event) => {
                    if (dragging === id) setTarget(hit(event));
                  }}
                  onPointerUp={(event) => {
                    if (dragging === id) {
                      const destination = hit(event);
                      if (destination) move(id, order.indexOf(destination));
                    }
                    setDragging(undefined);
                    setTarget(undefined);
                  }}
                  onPointerCancel={() => {
                    setDragging(undefined);
                    setTarget(undefined);
                  }}
                  onLostPointerCapture={() => {
                    setDragging(undefined);
                    setTarget(undefined);
                  }}
                >
                  <span aria-hidden="true">⠿</span>
                </button>
              </div>
            </li>
          );
        })}
      </ol>
      <details className="batting-stat-help">
        <summary>About these stats</summary>
        <p>
          AVG: batting average · OBP: on-base percentage · SLG: slugging
          percentage · OPS: OBP + SLG · HR: home runs · SB: stolen bases · SB%:
          stolen bases ÷ (stolen bases + caught stealing) · PA: plate
          appearances.
        </p>
        <p>
          All historical batting stints are combined. PA shows the sample size,
          not a limit on simulated playing time. Unknown stats display —. These
          are historical records; simulated results will vary.
        </p>
        <p>
          SB% displays — when there are no attempts or counts are unknown. Steal
          attempts are not currently modeled in the simulator.
        </p>
      </details>
      <button
        type="button"
        disabled={disabled}
        onClick={() =>
          onChange(
            defaultBattingOrder(draft),
            'Batting order reset to the default position order.',
          )
        }
      >
        Reset batting order
      </button>
    </section>
  );
}
