import { Model } from 'objection';

export class Customer extends Model {
  static tableName = 'customers';
  id!: number;
  name!: string;
  email!: string;
  phone?: string;
  address_line1?: string;
  city?: string;
  postcode?: string;
  country!: string;
  credit_limit!: number;
  created_at!: Date;
}
