import { CanActivateFn, Router } from '@angular/router';
import { inject } from '@angular/core';
import { AuthService } from './auth.service';

// UX only: hides routes from users without a token. The API still has to authorize
// every call; this guard must be reported as Info, not as a security control.
export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (auth.getToken() && !auth.isExpired()) {
    return true;
  }
  return router.createUrlTree(['/login']);
};
