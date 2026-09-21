const express = require('express');
const logger = require('./logger');
const authRoutes = require('./routes/auth');
const orderRoutes = require('./routes/orders');

const app = express();

app.use(express.json());
app.use('/auth', authRoutes);
app.use('/orders', orderRoutes);

app.use((err, req, res, next) => {
  logger.error({ err }, 'unhandled error');
  res.status(500).json({ error: 'internal error' });
});

app.listen(process.env.PORT || 3000, () => logger.info('api listening'));
