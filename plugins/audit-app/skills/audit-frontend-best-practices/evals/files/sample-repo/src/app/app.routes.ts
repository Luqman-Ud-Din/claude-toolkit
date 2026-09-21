import { Routes } from '@angular/router';
import { ReportsComponent } from './features/reports/reports.component';

export const routes: Routes = [
  { path: '', redirectTo: 'home', pathMatch: 'full' },
  {
    path: 'home',
    loadComponent: () => import('./features/home/home.component').then(m => m.HomeComponent),
  },
  {
    path: 'settings',
    loadChildren: () => import('./features/settings/settings.routes').then(m => m.SETTINGS_ROUTES),
  },
  // Reports is imported statically: it ships in the initial bundle
  { path: 'reports', component: ReportsComponent },
  { path: '**', redirectTo: 'home' },
];
