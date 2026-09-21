// In-memory stand-in for the users table.
const rows = [{ id: 'u1', email: 'ana@example.com', passwordHash: '$2a$10$abcdefghijklmnopqrstuv' }];

module.exports = {
  findByEmail: async (email) => rows.find((u) => u.email === email) || null,
  sendResetEmail: async () => undefined,
};
