import { z } from 'zod';

export const orderLineInput = z.object({
  productId: z.number().int().positive(),
  qty: z.number().int().min(1).max(10000)
});

export const createOrderInput = z.object({
  customerId: z.number().int().positive(),
  lines: z.array(orderLineInput).min(1)
});

export const createCustomerInput = z.object({
  name: z.string().min(1).max(200),
  email: z.string().email().max(254),
  phone: z.string().regex(/^\+?[0-9]{6,15}$/).optional(),
  addressLine1: z.string().max(200).optional(),
  city: z.string().max(100).optional(),
  postcode: z.string().regex(/^[0-9]{4}\s?[A-Z]{2}$/).optional(), // Dutch postcode format only
  creditLimit: z.number().min(0).default(0)
});
