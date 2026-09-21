import { Request, Response, NextFunction } from 'express';

// Single shared API key; there is no notion of user, role or tenant.
export function requireApiKey(req: Request, res: Response, next: NextFunction) {
  if (req.header('x-api-key') !== process.env.API_KEY) return res.status(401).json({ error: 'unauthorised' });
  next();
}
