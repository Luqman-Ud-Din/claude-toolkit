import { ChangeDetectionStrategy, Component, input } from '@angular/core';

export interface Tile { id: number; label: string; count: number; }

// Negative control: standalone, OnPush, signal input, new control flow with track.
@Component({
  selector: 'app-home',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (tiles().length === 0) {
      <p>Nothing to show.</p>
    } @else {
      @for (t of tiles(); track t.id) {
        <div class="tile">{{ t.label }}: {{ t.count }}</div>
      }
    }
  `,
})
export class HomeComponent {
  tiles = input<Tile[]>([]);
}
