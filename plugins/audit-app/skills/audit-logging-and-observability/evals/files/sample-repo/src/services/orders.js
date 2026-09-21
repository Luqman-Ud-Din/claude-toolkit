const axios = require('axios');
const logger = require('../logger');

const INVENTORY_URL = process.env.INVENTORY_URL || 'http://inventory:8080';

async function reserveStock(order) {
  try {
    await axios.post(`${INVENTORY_URL}/reservations`, { sku: order.sku, qty: order.qty });
    return true;
  } catch (err) {
    logger.debug('could not reserve stock', err);
    return true;
  }
}

async function capturePayment(order, gateway) {
  try {
    return await gateway.capture(order.paymentId, order.total);
  } catch (err) {
    logger.error({ err, orderId: order.id }, 'payment capture failed');
    throw err;
  }
}

async function createOrder(input, gateway) {
  const order = { id: Date.now().toString(), ...input };
  logger.info('order created ' + order.id);
  await reserveStock(order);
  await capturePayment(order, gateway);
  return order;
}

module.exports = { createOrder, reserveStock, capturePayment };
