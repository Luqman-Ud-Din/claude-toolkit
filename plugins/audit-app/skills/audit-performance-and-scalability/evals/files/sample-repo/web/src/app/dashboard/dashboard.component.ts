import { Component, OnInit } from '@angular/core';
import { ApiService } from '../core/api.service';
import { UnitsService } from '../core/units.service';

interface Product { id: number; name: string; price: number; stock: number; categoryId: number }

@Component({
  selector: 'app-dashboard',
  template: `
    <section>{{ lowStockCount }} low stock</section>
    <section>{{ totalValue }} inventory value</section>
    <section>{{ topProducts.length }} top products</section>
    <section>{{ categoryCount }} categories</section>
    <section>{{ recent.length }} recent</section>
  `,
})
export class DashboardComponent implements OnInit {
  lowStockCount = 0; totalValue = 0; topProducts: Product[] = []; categoryCount = 0; recent: Product[] = [];

  constructor(private api: ApiService, private units: UnitsService) {}

  // PERF (CALLS-PER-PAGE): the same GET /api/products request is issued five times on load,
  // once per widget. One fetch shared across widgets (or shareReplay in the service) would do.
  ngOnInit(): void {
    this.api.get<Product[]>('products').subscribe(p => this.lowStockCount = p.filter(x => x.stock < 5).length);
    this.api.get<Product[]>('products').subscribe(p => this.totalValue = p.reduce((s, x) => s + x.price * x.stock, 0));
    this.api.get<Product[]>('products').subscribe(p => this.topProducts = p.slice(0, 5));
    this.api.get<Product[]>('products').subscribe(p => this.categoryCount = new Set(p.map(x => x.categoryId)).size);
    this.api.get<Product[]>('products').subscribe(p => this.recent = p.slice(-5));

    // OK: reference data cached in the service (shareReplay) - one request per session.
    this.units.getUnits().subscribe();
  }
}
