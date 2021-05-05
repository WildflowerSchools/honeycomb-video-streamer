require("dotenv").config()
const express = require("express")

const morganMiddleware = require('./morganMiddleware').default
const auth = require("./auth")
const videos = require("./videos")
const errors = require("./errors")

const applyAuth = auth.apply
const applyVideos = videos.apply
const applyErrors = errors.apply

const port = process.env.SERVICE_PORT ? process.env.SERVICE_PORT : 8000

let app

if (process.env.ENVIRONMENT === "production") {
  app = express()
} else {
  app = require("https-localhost")()
}

console.log("setting up")

app.use(morganMiddleware)
applyAuth(app)
applyVideos(app)
applyErrors(app)

console.log("listening")

// Allow ctrl-c to work in docker
process.on('SIGINT', () => {
  console.info("Interrupted")
  process.exit(0)
})

app.listen(port, () => console.log(`Listening on port ${port}!`))
