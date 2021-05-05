const morgan = require("morgan")

const morganMiddleware = morgan(
  ":method :url :status :res[content-length] - :response-time ms",
  {}
)

exports.default = morganMiddleware
