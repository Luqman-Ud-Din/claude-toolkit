import { Router } from 'express';
import { OrdersService } from './orders.service';

export const ordersRouter = Router();
const orders = new OrdersService();

ordersRouter.post('/orders', async (req, res) => {
  const result = await orders.create(req.body);
  res.status(201).json(result);
});

ordersRouter.get('/orders/:id/availability', async (req, res) => {
  res.json(await orders.availability(req.params.id));
});
