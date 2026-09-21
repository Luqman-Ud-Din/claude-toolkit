exports.up = async function (knex) {
  await knex.schema.createTable('customers', (t) => {
    t.increments('id');
    t.string('name', 200).notNullable();
    t.string('email', 254).notNullable();
    t.string('phone', 20);
    t.string('address_line1', 200);
    t.string('city', 100);
    t.string('postcode', 10);
    t.string('country', 2).notNullable().defaultTo('NL');
    t.decimal('credit_limit', 12, 2).notNullable().defaultTo(0);
    t.timestamp('created_at').notNullable().defaultTo(knex.fn.now());
  });
};
exports.down = async function (knex) {
  await knex.schema.dropTable('customers');
};
