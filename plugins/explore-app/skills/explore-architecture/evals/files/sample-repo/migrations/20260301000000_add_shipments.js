exports.up = async function (knex) {
  await knex.schema.createTable('shipments', (t) => {
    t.increments('id');
    t.integer('order_id').notNullable().references('id').inTable('orders');
    t.string('carrier', 50).notNullable();
    t.string('tracking_no', 64);
    t.decimal('weight_kg', 8, 3);
    t.timestamp('shipped_at');
    t.timestamp('delivered_at');
    t.index(['order_id']);
  });
  await knex.schema.alterTable('products', (t) => {
    t.integer('reorder_level').notNullable().defaultTo(0);
  });
};
exports.down = async function (knex) {
  await knex.schema.alterTable('products', (t) => { t.dropColumn('reorder_level'); });
  await knex.schema.dropTable('shipments');
};
