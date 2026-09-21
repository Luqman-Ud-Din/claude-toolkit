import { Model } from 'objection';
import { Customer } from './customer.model';
import { Product } from './product.model';

export type OrderStatus = 'draft' | 'confirmed' | 'paid' | 'shipped' | 'delivered' | 'cancelled';

export class OrderLine extends Model {
  static tableName = 'order_lines';
  id!: number;
  order_id!: number;
  product_id!: number;
  qty!: number;
  unit_price!: number;
  line_total!: number;

  static relationMappings = {
    // Declared in the ORM, but the migrations never created a foreign key for order_lines.product_id.
    product: {
      relation: Model.BelongsToOneRelation,
      modelClass: Product,
      join: { from: 'order_lines.product_id', to: 'products.id' }
    }
  };
}

export class Order extends Model {
  static tableName = 'orders';
  id!: number;
  customer_id!: number;
  order_no!: string;
  status!: OrderStatus;
  subtotal!: number;
  tax!: number;
  total!: number;
  placed_at?: Date;
  paid_at?: Date;
  created_at!: Date;
  lines?: OrderLine[];
  customer?: Customer;

  static relationMappings = {
    customer: {
      relation: Model.BelongsToOneRelation,
      modelClass: Customer,
      join: { from: 'orders.customer_id', to: 'customers.id' }
    },
    lines: {
      relation: Model.HasManyRelation,
      modelClass: OrderLine,
      join: { from: 'orders.id', to: 'order_lines.order_id' }
    }
  };
}
