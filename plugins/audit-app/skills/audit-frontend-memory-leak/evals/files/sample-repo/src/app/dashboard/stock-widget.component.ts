import { AfterViewInit, Component, DestroyRef, ElementRef, ViewChild, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { interval } from 'rxjs';
import { Chart } from 'chart.js';
import { SalesService } from './sales.service';

// Negative control: every acquisition is released via DestroyRef / takeUntilDestroyed.
@Component({
  selector: 'app-stock-widget',
  standalone: true,
  template: `<div #host><canvas #canvas></canvas></div>`,
})
export class StockWidgetComponent implements AfterViewInit {
  @ViewChild('host') host!: ElementRef<HTMLElement>;
  @ViewChild('canvas') canvas!: ElementRef<HTMLCanvasElement>;
  private destroyRef = inject(DestroyRef);
  private sales = inject(SalesService);
  private chart?: Chart;
  private ro?: ResizeObserver;
  private onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') this.chart?.reset(); };

  ngAfterViewInit(): void {
    this.chart = new Chart(this.canvas.nativeElement, { type: 'line', data: { datasets: [] } });
    this.ro = new ResizeObserver(() => this.chart?.resize());
    this.ro.observe(this.host.nativeElement);
    window.addEventListener('keydown', this.onKey);
    const timer = setInterval(() => this.chart?.update(), 30000);
    interval(10000).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => this.sales.load());
    this.destroyRef.onDestroy(() => {
      clearInterval(timer);
      window.removeEventListener('keydown', this.onKey);
      this.ro?.disconnect();
      this.chart?.destroy();
    });
  }
}
