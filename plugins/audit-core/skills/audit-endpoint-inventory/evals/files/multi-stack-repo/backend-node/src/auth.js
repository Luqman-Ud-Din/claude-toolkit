exports.requireAuth = (req, res, next) => (req.user ? next() : res.status(401).end());
