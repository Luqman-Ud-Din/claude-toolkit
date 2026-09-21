exports.up = async function (knex) {
  await knex.schema.createTable('orders', (t) => {
    t.increments('id');
    t.integer('customer_id').notNullable().references('id').inTable('customers');
    t.string('order_no', 32).notNullable();
    t.string('status', 20).notNullable().defaultTo('draft');
    t.decimal('subtotal', 12, 2).notNullable().defaultTo(0);
    t.decimal('tax', 12, 2).notNullable().defaultTo(0);
    t.decimal('total', 12, 2).notNullable().defaultTo(0);
    t.timestamp('placed_at');
    t.timestamp('created_at').notNullable().defaultTo(knex.fn.now());
    t.index(['customer_id']);
  });
  await knex.schema.createTable('order_lines', (t) => {
    t.increments('id');
    t.integer('order_id').notNullable().references('id').inTable('orders').onDelete('CASCADE');
    t.integer('product_id').notNullable();
    t.integer('qty').notNullable();
    t.decimal('unit_price', 12, 2).notNullable();
    t.decimal('line_total', 12, 2).notNullable();
  });
};
exports.down = async function (knex) {
  await knex.schema.dropTable('order_lines');
  await knex.schema.dropTable('orders');
};
