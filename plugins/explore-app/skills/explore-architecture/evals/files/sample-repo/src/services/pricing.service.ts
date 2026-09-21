import { Product } from '../models/product.model';

// Volume discount: 5% off a line when qty >= 100, 10% when qty >= 500.
export function lineTotal(product: Product, qty: number): number {
  let unit = product.unit_price;
  if (qty >= 500) unit = unit * 0.9;
  else if (qty >= 100) unit = unit * 0.95;
  return Math.round(unit * qty * 100) / 100;
}
