import { Request, Response } from 'express';
import { CustomerService } from '../services/customer.service';
import { createCustomerInput } from '../validators/order.schema';

const customers = new CustomerService();

export async function create(req: Request, res: Response) {
  const input = createCustomerInput.parse(req.body);
  const customer = await customers.create(input);
  res.status(201).json(customer);
}
