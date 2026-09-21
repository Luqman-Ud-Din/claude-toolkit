import { AfterViewInit, Component, ElementRef, OnInit, ViewChild } from '@angular/core';
import { interval } from 'rxjs';
import { Chart } from 'chart.js';
import { SalesService } from './sales.service';

@Component({
  selector: 'app-sales-chart',
  standalone: true,
  template: `<canvas #canvas></canvas><p>{{ total }}</p>`,
})
export class SalesChartComponent implements OnInit, AfterViewInit {
  @ViewChild('canvas') canvas!: ElementRef<HTMLCanvasElement>;
  total = 0;
  private chart?: Chart;

  constructor(private sales: SalesService) {}

  ngOnInit(): void {
    // bare subscribe on a stream that never completes
    this.sales.totals$.subscribe(t => (this.total = t));
    interval(5000).subscribe(() => this.refresh());
  }

  ngAfterViewInit(): void {
    this.chart = new Chart(this.canvas.nativeElement, { type: 'bar', data: { datasets: [] } });
    window.addEventListener('resize', () => this.chart?.resize());
  }

  private refresh(): void {
    this.chart?.update();
  }
}
