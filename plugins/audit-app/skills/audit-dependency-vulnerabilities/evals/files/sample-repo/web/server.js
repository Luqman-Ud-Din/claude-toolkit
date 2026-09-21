const express = require('express');
const _ = require('lodash');
const app = express();
app.use(express.json());
app.post('/api/profile', (req, res) => {
  const profile = _.merge({}, req.body);   // user-controlled input reaches lodash.merge
  res.json(profile);
});
app.listen(3000);
