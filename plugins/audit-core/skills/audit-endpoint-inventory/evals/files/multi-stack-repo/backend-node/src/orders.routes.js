const { Router } = require('express');
const axios = require('axios');
const { requireAuth } = require('./auth');
const db = require('./db');

const router = Router();
const customersClient = axios.create({ baseURL: process.env.CUSTOMERS_URL });
const pricingClient = axios.create({ baseURL: process.env.PRICING_URL });
const taxClient = axios.create({ baseURL: process.env.TAX_URL });

// Planted: three independent outbound calls awaited one after another.
router.post('/orders', requireAuth, async (req, res) => {
  const customer = await customersClient.get(`/customers/${req.body.customerId}`);
  const quote = await pricingClient.post('/quotes', { items: req.body.items });
  const tax = await taxClient.get(`/rates/${req.body.region}`);
  res.status(201).json({ customer: customer.data.name, total: quote.data.total * (1 + tax.data.rate) });
});

router.get('/orders/:orderId', requireAuth, async (req, res) => {
  const order = await db.orders.findOne({ where: { id: req.params.orderId, userId: req.user.id } });
  res.json(order);
});

module.exports = router;
