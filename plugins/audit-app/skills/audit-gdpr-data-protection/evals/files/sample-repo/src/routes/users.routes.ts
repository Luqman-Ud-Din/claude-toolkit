import { Router } from 'express';
import { UserService } from '../services/user.service';

const router = Router();
const users = new UserService();

router.post('/users', async (req, res) => {
  const user = await users.register(req.body);
  res.status(201).json({ id: user.id });
});

router.get('/users/:id', async (req, res) => {
  const user = await users.findById(req.params.id);
  res.json(user);
});

router.put('/users/:id', async (req, res) => {
  const user = await users.update(req.params.id, req.body);
  res.json(user);
});

// Logout: removes the session token. This is NOT account deletion.
router.delete('/sessions/:token', async (req, res) => {
  await users.revokeSession(req.params.token);
  res.status(204).end();
});

export default router;
