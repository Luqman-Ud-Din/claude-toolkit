import { Product } from '../models/product.model';
import { OrderService } from './order.service'; // circular: order.service imports inventory.service

export class InventoryService {
  async reserve(productId: number, qty: number): Promise<void> {
    const product = await Product.query().findById(productId);
    if (!product || !product.is_active) throw new Error('Product unavailable');
    if (product.stock_on_hand < qty) throw new Error('Insufficient stock for ' + product.sku);
    await Product.query().findById(productId).patch({ stock_on_hand: product.stock_on_hand - qty });
  }

  async release(productId: number, qty: number): Promise<void> {
    const product = await Product.query().findById(productId);
    if (!product) return;
    await Product.query().findById(productId).patch({ stock_on_hand: product.stock_on_hand + qty });
  }

  // Low-stock report also lists the open orders that consume the product.
  async lowStock(): Promise<Array<{ product: Product; openOrders: number }>> {
    const products = await Product.query().whereRaw('stock_on_hand <= reorder_level');
    const orders = new OrderService();
    const out = [];
    for (const p of products) {
      out.push({ product: p, openOrders: await orders.countOpenForProduct(p.id) });
    }
    return out;
  }
}
