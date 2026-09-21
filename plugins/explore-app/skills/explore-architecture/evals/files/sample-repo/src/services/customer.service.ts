import { Customer } from '../models/customer.model';

export class CustomerService {
  // Uniqueness of email is only checked here; the customers table has no unique constraint on email.
  async create(input: { name: string; email: string; phone?: string; addressLine1?: string; city?: string; postcode?: string; creditLimit: number }) {
    const existing = await Customer.query().findOne({ email: input.email.toLowerCase() });
    if (existing) throw new Error('A customer with this email already exists');
    return Customer.query().insert({
      name: input.name,
      email: input.email.toLowerCase(),
      phone: input.phone,
      address_line1: input.addressLine1,
      city: input.city,
      postcode: input.postcode,
      credit_limit: input.creditLimit
    });
  }

  // Credit check: open (unpaid, not cancelled) order totals plus the new order must not exceed the credit limit.
  async assertWithinCreditLimit(customerId: number, newOrderTotal: number): Promise<void> {
    const customer = await Customer.query().findById(customerId);
    if (!customer) throw new Error('Customer not found');
    const { Order } = await import('../models/order.model');
    const open = await Order.query()
      .where({ customer_id: customerId })
      .whereIn('status', ['confirmed', 'shipped', 'delivered'])
      .whereNull('paid_at')
      .sum('total as total')
      .first();
    const exposure = Number((open as any)?.total ?? 0) + newOrderTotal;
    if (exposure > customer.credit_limit) {
      throw new Error('Credit limit exceeded: exposure ' + exposure + ' > limit ' + customer.credit_limit);
    }
  }
}
