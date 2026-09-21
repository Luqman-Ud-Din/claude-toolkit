const express = require('express');
const { createOrder } = require('../services/orders');

const router = express.Router();
const gateway = { capture: async (paymentId, amount) => ({ paymentId, amount, status: 'captured' }) };

router.post('/', async (req, res, next) => {
  try {
    const order = await createOrder(req.body, gateway);
    res.status(201).json(order);
  } catch (err) {
    next(err);
  }
});

module.exports = router;
