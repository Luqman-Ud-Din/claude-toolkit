import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class SalesService {
  private readonly totals = new BehaviorSubject<number>(0);
  readonly totals$: Observable<number> = this.totals.asObservable();
  private listeners: Array<(n: number) => void> = [];

  constructor(private http: HttpClient) {}

  register(cb: (n: number) => void): void {
    // grows per component instance; there is no unregister()
    this.listeners.push(cb);
  }

  load(): void {
    this.http.get<number>('/api/sales/total').subscribe(t => {
      this.totals.next(t);
      this.listeners.forEach(l => l(t));
    });
  }
}
