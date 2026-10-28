import { useRef, useState, type PointerEvent } from 'react';
import type { DraftEngine, DraftState } from '../draft/engine';
import {
  defaultBattingOrder,
  moveBatter,
  type BattingOrder,
} from '../draft/batting-order';

export default function BattingOrderEditor({
  engine,
  draft,
  order,
  disabled,
  onChange,
}: {
  engine: DraftEngine;
  draft: DraftState;
  order: BattingOrder;
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
      <h2 id="batting-order-title">Batting order</h2>
      <p id="batting-order-help" className="muted">
        Drag a handle or use Move up and Move down. A focused handle also
        accepts Arrow Up/Down. Fielding positions stay assigned.
      </p>
      <ol ref={list} aria-label="Batting order" className="batting-order">
        {order.map((id, i) => {
          const player = engine.player(id);
          const pick = draft.history.find((p) => p.playerId === id)!;
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
                {player.name}
                <small>{pick.position}</small>
              </span>
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
