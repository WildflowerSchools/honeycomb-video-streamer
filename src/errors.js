function logErrors(err, req, res, next) {
  if (err.stack) {
    console.error(err.stack)
  } else {
    console.error(err)
  }
  next(err)
}

function clientErrorHandler(err, req, res, next) {
  if (req.xhr || /^application\/json/.test(req.headers.accept)) {
    res.status(500).json({ error: "Unexpected error" })
  } else {
    next(err)
  }
}

function errorHandler(err, req, res, next) {
  res.status(500).end()
}

exports.apply = function(app) {
  app.get("/", (req, res, next) => {
    res.status(200).json({ error: "nothing to see here" })
  })
  app.use(logErrors)
  app.use(clientErrorHandler)
  app.use(errorHandler)
}
