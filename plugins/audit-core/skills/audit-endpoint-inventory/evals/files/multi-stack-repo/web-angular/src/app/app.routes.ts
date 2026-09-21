import { Routes } from '@angular/router';
import { authGuard } from './auth.guard';

export const routes: Routes = [
  { path: 'login', loadComponent: () => import('./login.component').then(m => m.LoginComponent) },
  {
    path: 'admin',
    canActivate: [authGuard],
    data: { roles: ['Admin'] },
    children: [
      { path: 'users', loadComponent: () => import('./users.component').then(m => m.UsersComponent) },
    ],
  },
];
