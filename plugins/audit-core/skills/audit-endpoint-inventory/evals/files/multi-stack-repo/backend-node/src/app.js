const express = require('express');
const ordersRouter = require('./orders.routes');

const app = express();
app.use(express.json());
app.use('/api', ordersRouter);
app.listen(3000);
