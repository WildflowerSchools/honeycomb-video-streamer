require('dotenv').config();
const express = require('express');
const auth = require('./auth');
const videos = require('./videos');
const applyAuth = auth.apply
const applyVideos = videos.apply


const port = process.env.SERVICE_PORT ? process.env.SERVICE_PORT : 8000

var app;


if (process.env.ENVIRONMENT === "production") {
    app = express()
} else {
    app = require("https-localhost")()
}

console.log('setting up')

applyAuth(app)
applyVideos(app)

console.log('listening')

app.listen(port, () => console.log(`Example app listening on port ${port}!`))
