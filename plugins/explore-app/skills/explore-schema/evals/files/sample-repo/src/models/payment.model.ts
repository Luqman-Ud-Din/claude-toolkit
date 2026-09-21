import { Model } from 'objection';
import { Order } from './order.model';

export class Payment extends Model {
  static tableName = 'payments';
  id!: number;
  order_id!: number;
  provider_ref?: string;
  amount!: number;
  status!: 'pending' | 'succeeded' | 'failed';
  paid_at?: Date;
  created_at!: Date;

  static relationMappings = {
    order: {
      relation: Model.BelongsToOneRelation,
      modelClass: Order,
      join: { from: 'payments.order_id', to: 'orders.id' }
    }
  };
}
