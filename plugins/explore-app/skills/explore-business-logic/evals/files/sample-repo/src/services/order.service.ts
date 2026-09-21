import { Order, OrderLine, OrderStatus } from '../models/order.model';
import { Product } from '../models/product.model';
import { InventoryService } from './inventory.service';
import { CustomerService } from './customer.service';
import { lineTotal } from './pricing.service';
import { sendEmail } from '../integrations/email';

const TRANSITIONS: Record<OrderStatus, OrderStatus[]> = {
  draft: ['confirmed', 'cancelled'],
  confirmed: ['paid', 'cancelled'],
  paid: ['shipped'],
  shipped: ['delivered'],
  delivered: [],
  cancelled: []
};

export class OrderService {
  private inventory = new InventoryService();
  private customers = new CustomerService();

  async createDraft(customerId: number, lines: Array<{ productId: number; qty: number }>): Promise<Order> {
    const products = await Product.query().findByIds(lines.map((l) => l.productId));
    const byId = new Map(products.map((p) => [p.id, p]));
    let subtotal = 0;
    const lineRows: Partial<OrderLine>[] = [];
    for (const l of lines) {
      const p = byId.get(l.productId);
      if (!p) throw new Error('Unknown product ' + l.productId);
      const total = lineTotal(p, l.qty);
      subtotal += total;
      lineRows.push({ product_id: p.id, qty: l.qty, unit_price: p.unit_price, line_total: total });
    }
    const orderNo = 'ORD-' + Date.now();
    return Order.query().insertGraph({ customer_id: customerId, order_no: orderNo, status: 'draft', subtotal, tax: 0, total: subtotal, lines: lineRows } as any);
  }

  async transition(orderId: number, to: OrderStatus): Promise<Order> {
    const order = await Order.query().findById(orderId).withGraphFetched('lines');
    if (!order) throw new Error('Order not found');
    if (!TRANSITIONS[order.status].includes(to)) {
      throw new Error('Cannot move order from ' + order.status + ' to ' + to);
    }
    if (to === 'confirmed') {
      await this.customers.assertWithinCreditLimit(order.customer_id, order.total);
      for (const l of order.lines ?? []) await this.inventory.reserve(l.product_id, l.qty);
      await Order.query().findById(orderId).patch({ status: to, placed_at: new Date() });
    } else if (to === 'cancelled') {
      if (order.status === 'confirmed') {
        for (const l of order.lines ?? []) await this.inventory.release(l.product_id, l.qty);
      }
      await Order.query().findById(orderId).patch({ status: to });
    } else {
      await Order.query().findById(orderId).patch({ status: to });
    }
    if (to === 'shipped') {
      const withCustomer = await Order.query().findById(orderId).withGraphFetched('customer');
      await sendEmail(withCustomer!.customer!.email, 'Order ' + order.order_no + ' shipped', 'Your order is on its way.');
    }
    return (await Order.query().findById(orderId))!;
  }

  async countOpenForProduct(productId: number): Promise<number> {
    const r = await OrderLine.query()
      .join('orders', 'orders.id', 'order_lines.order_id')
      .where('order_lines.product_id', productId)
      .whereIn('orders.status', ['confirmed', 'paid'])
      .count('order_lines.id as n')
      .first();
    return Number((r as any)?.n ?? 0);
  }
}
