import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_KEY || '', { apiVersion: '2023-10-16' });

// Takes payment for an order total. Amounts are always charged in EUR.
export async function charge(amount: number, reference: string): Promise<{ id: string; ok: boolean }> {
  const intent = await stripe.paymentIntents.create({
    amount: Math.round(amount * 100),
    currency: 'eur',
    description: reference,
    confirm: true
  });
  return { id: intent.id, ok: intent.status === 'succeeded' };
}
