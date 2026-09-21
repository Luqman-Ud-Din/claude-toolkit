import { Request, Response } from 'express';
import { Shipment } from '../models/shipment.model';
import { Order } from '../models/order.model';
import { OrderService } from '../services/order.service';

const orders = new OrderService();

// Shipping is driven directly from the controller: creates the shipment row, then moves the order.
export async function ship(req: Request, res: Response) {
  const order = await Order.query().findById(Number(req.params.id));
  if (!order) return res.status(404).end();
  if (order.status !== 'paid') return res.status(409).json({ error: 'Only paid orders can be shipped' });
  const shipment = await Shipment.query().insert({
    order_id: order.id,
    carrier: req.body.carrier ?? 'PostNL',
    tracking_no: req.body.trackingNo,
    weight_kg: req.body.weightKg,
    shipped_at: new Date()
  });
  await orders.transition(order.id, 'shipped');
  res.status(201).json(shipment);
}

export async function deliver(req: Request, res: Response) {
  const shipment = await Shipment.query().findOne({ order_id: Number(req.params.id) });
  if (!shipment) return res.status(404).end();
  await Shipment.query().findById(shipment.id).patch({ delivered_at: new Date() });
  await orders.transition(Number(req.params.id), 'delivered');
  res.json({ ok: true });
}
