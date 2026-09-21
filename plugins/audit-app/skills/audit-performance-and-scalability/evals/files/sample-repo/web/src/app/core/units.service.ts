import { Injectable } from '@angular/core';
import { Observable, shareReplay } from 'rxjs';
import { ApiService } from './api.service';

export interface Unit { id: number; name: string }

// OK: reference data fetched once and replayed - must NOT be flagged as uncached.
@Injectable({ providedIn: 'root' })
export class UnitsService {
  private units$?: Observable<Unit[]>;
  constructor(private api: ApiService) {}
  getUnits(): Observable<Unit[]> {
    return (this.units$ ??= this.api.get<Unit[]>('units').pipe(shareReplay({ bufferSize: 1, refCount: false })));
  }
}
