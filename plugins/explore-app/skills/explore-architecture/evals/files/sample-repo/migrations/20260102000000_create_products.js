exports.up = async function (knex) {
  await knex.schema.createTable('products', (t) => {
    t.increments('id');
    t.string('sku', 64).notNullable();
    t.string('name', 200).notNullable();
    t.decimal('unit_price', 12, 2).notNullable();
    t.integer('stock_on_hand').notNullable().defaultTo(0);
    t.boolean('is_active').notNullable().defaultTo(true);
    t.timestamp('created_at').notNullable().defaultTo(knex.fn.now());
    t.unique(['sku']);
  });
};
exports.down = async function (knex) {
  await knex.schema.dropTable('products');
};
