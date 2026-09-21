const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const logger = require('../logger');
const users = require('../repositories/users');

const router = express.Router();

router.post('/login', async (req, res) => {
  logger.info({ body: req.body }, 'login attempt');
  const user = await users.findByEmail(req.body.email);
  if (!user || !(await bcrypt.compare(req.body.password, user.passwordHash))) {
    logger.warn({ userId: user ? user.id : null }, 'login failed');
    return res.status(401).json({ error: 'invalid credentials' });
  }
  logger.info({ userId: user.id }, 'login succeeded');
  return res.json({ token: jwt.sign({ sub: user.id }, process.env.JWT_SECRET, { expiresIn: '15m' }) });
});

router.post('/forgot-password', async (req, res) => {
  await users.sendResetEmail(req.body.email);
  logger.info('password reset email sent');
  res.status(202).end();
});

module.exports = router;
