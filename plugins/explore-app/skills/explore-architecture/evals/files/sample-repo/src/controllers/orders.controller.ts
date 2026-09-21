import { Request, Response } from 'express';
import { OrderService } from '../services/order.service';
import { Order } from '../models/order.model';
import { Payment } from '../models/payment.model';
import { createOrderInput } from '../validators/order.schema';
import { charge } from '../integrations/payment.gateway';

const orders = new OrderService();

export async function create(req: Request, res: Response) {
  const input = createOrderInput.parse(req.body);
  const order = await orders.createDraft(input.customerId, input.lines);
  res.status(201).json(order);
}

export async function confirm(req: Request, res: Response) {
  const order = await Order.query().findById(Number(req.params.id)).withGraphFetched('customer');
  if (!order) return res.status(404).end();
  // Tax is computed here, in the controller, with the rate chosen by a country conditional.
  let rate = 0;
  if (order.customer!.country === 'NL') rate = 0.21;
  else if (order.customer!.country === 'BE') rate = 0.21;
  else if (order.customer!.country === 'DE') rate = 0.19;
  const tax = Math.round(order.subtotal * rate * 100) / 100;
  await Order.query().findById(order.id).patch({ tax, total: order.subtotal + tax });
  const updated = await orders.transition(order.id, 'confirmed');
  res.json(updated);
}

export async function pay(req: Request, res: Response) {
  const order = await Order.query().findById(Number(req.params.id));
  if (!order) return res.status(404).end();
  if (order.status !== 'confirmed') return res.status(409).json({ error: 'Order must be confirmed before payment' });
  const result = await charge(order.total, order.order_no);
  await Payment.query().insert({
    order_id: order.id,
    provider_ref: result.id,
    amount: order.total,
    status: result.ok ? 'succeeded' : 'failed',
    paid_at: result.ok ? new Date() : undefined
  });
  if (!result.ok) return res.status(402).json({ error: 'Payment failed' });
  await Order.query().findById(order.id).patch({ paid_at: new Date() });
  const updated = await orders.transition(order.id, 'paid');
  res.json(updated);
}

export async function cancel(req: Request, res: Response) {
  const updated = await orders.transition(Number(req.params.id), 'cancelled');
  res.json(updated);
}

export async function list(req: Request, res: Response) {
  const page = Number(req.query.page ?? 1);
  const rows = await Order.query().orderBy('created_at', 'desc').page(page - 1, 25);
  res.json(rows);
}
