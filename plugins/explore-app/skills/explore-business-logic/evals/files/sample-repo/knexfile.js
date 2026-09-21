module.exports = {
  client: 'pg',
  connection: process.env.DATABASE_URL || 'postgres://orderly:orderly@localhost:5432/orderly',
  migrations: { directory: './migrations' }
};
