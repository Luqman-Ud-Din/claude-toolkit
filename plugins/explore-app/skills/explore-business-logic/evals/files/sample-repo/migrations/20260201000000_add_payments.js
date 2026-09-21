exports.up = async function (knex) {
  await knex.schema.createTable('payments', (t) => {
    t.increments('id');
    t.integer('order_id').notNullable().references('id').inTable('orders');
    t.string('provider_ref', 100);
    t.decimal('amount', 12, 2).notNullable();
    t.string('status', 20).notNullable().defaultTo('pending');
    t.timestamp('paid_at');
    t.timestamp('created_at').notNullable().defaultTo(knex.fn.now());
  });
  await knex.schema.alterTable('orders', (t) => {
    t.timestamp('paid_at');
  });
};
exports.down = async function (knex) {
  await knex.schema.alterTable('orders', (t) => { t.dropColumn('paid_at'); });
  await knex.schema.dropTable('payments');
};
