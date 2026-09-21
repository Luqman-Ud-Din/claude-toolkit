import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, tap } from 'rxjs';
import { jwtDecode } from 'jwt-decode';
import { environment } from '../../environments/environment';

interface LoginResponse {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  constructor(private http: HttpClient, private router: Router) {}

  login(username: string, password: string): Observable<LoginResponse> {
    return this.http
      .post<LoginResponse>(`${environment.apiUrl}/auth/login`, { username, password })
      .pipe(tap((res) => this.setSession(res)));
  }

  private setSession(res: LoginResponse): void {
    // ISSUE (planted): both tokens go to localStorage - readable by any script on the origin,
    // and the refresh token lives there for as long as the browser profile exists.
    localStorage.setItem('access_token', res.accessToken);
    localStorage.setItem('refresh_token', res.refreshToken);
    localStorage.setItem('user', JSON.stringify(jwtDecode(res.accessToken)));
  }

  getToken(): string | null {
    return localStorage.getItem('access_token');
  }

  isExpired(): boolean {
    const token = this.getToken();
    if (!token) return true;
    const { exp } = jwtDecode<{ exp: number }>(token);
    return Date.now() >= exp * 1000;
  }

  refreshToken(): Observable<LoginResponse> {
    // No single-flight guard: several 401s in parallel trigger several refresh calls.
    const refresh = localStorage.getItem('refresh_token');
    return this.http
      .post<LoginResponse>(`${environment.apiUrl}/auth/refresh`, { refreshToken: refresh })
      .pipe(tap((res) => this.setSession(res)));
  }

  logout(): void {
    // ISSUE (planted): only the access token is removed; refresh_token and user survive logout.
    localStorage.removeItem('access_token');
    this.router.navigate(['/login']);
  }
}
