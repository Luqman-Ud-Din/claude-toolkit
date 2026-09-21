import { Model } from 'objection';

export class Product extends Model {
  static tableName = 'products';
  id!: number;
  sku!: string;
  name!: string;
  unit_price!: number;
  stock_on_hand!: number;
  reorder_level!: number;
  is_active!: boolean;
  created_at!: Date;
}
