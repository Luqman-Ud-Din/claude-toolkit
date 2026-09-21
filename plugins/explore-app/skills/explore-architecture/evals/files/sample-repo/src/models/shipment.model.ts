import { Model } from 'objection';

export class Shipment extends Model {
  static tableName = 'shipments';
  id!: number;
  order_id!: number;
  carrier!: string;
  tracking_no?: string;
  weight_kg?: number;
  shipped_at?: Date;
  delivered_at?: Date;
}
