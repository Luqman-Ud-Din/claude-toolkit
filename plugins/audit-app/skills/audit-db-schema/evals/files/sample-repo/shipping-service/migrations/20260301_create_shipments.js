// Planted issue: Knex migration with no down() - cannot be rolled back.
// Also: shipping_cost as float, order_id FK without index, naive timestamps.
exports.up = async function (knex) {
  await knex.schema.createTable('shipments', (t) => {
    t.increments('id');
    t.integer('order_id').notNullable().references('id').inTable('orders');
    t.string('tracking_no', 64).notNullable();
    t.float('shipping_cost').notNullable();
    t.timestamp('shipped_at');
    t.timestamps();
  });
};
