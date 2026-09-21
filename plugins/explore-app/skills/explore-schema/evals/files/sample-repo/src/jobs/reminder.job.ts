import cron from 'node-cron';
import Knex from 'knex';
import { Model } from 'objection';
import { Order } from '../models/order.model';
import { sendEmail } from '../integrations/email';

Model.knex(Knex(require('../../knexfile')));

// Every day at 09:00 server time: remind customers of confirmed orders unpaid for more than 7 days.
cron.schedule('0 9 * * *', async () => {
  const cutoff = new Date(Date.now() - 7 * 24 * 3600 * 1000);
  const overdue = await Order.query()
    .where({ status: 'confirmed' })
    .whereNull('paid_at')
    .where('placed_at', '<', cutoff)
    .withGraphFetched('customer');
  for (const o of overdue) {
    await sendEmail(o.customer!.email, 'Payment reminder for ' + o.order_no, 'Order total ' + o.total.toFixed(2) + ' EUR is due.');
  }
});
