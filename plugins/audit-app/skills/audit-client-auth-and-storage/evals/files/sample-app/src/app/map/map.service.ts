import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../environments/environment';

// Third-party call made through the shared HttpClient - the token interceptor
// attaches the user's bearer token to this request too.
@Injectable({ providedIn: 'root' })
export class MapService {
  constructor(private http: HttpClient) {}

  geocode(address: string) {
    return this.http.get(`${environment.mapsUrl}/geocode/json`, {
      params: { address, key: environment.mapsBrowserKey },
    });
  }
}
