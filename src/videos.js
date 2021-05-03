const express = require("express")
const cors = require("cors")
const path = require("path")
const securedSessionOrJWT = require("./auth").securedSessionOrJWT

const PUBLIC_PATH = process.env.PUBLIC_PATH ? process.env.PUBLIC_PATH : path.resolve(
  __dirname,
  "public"
)

const CONTENT_TYPE = {
  MANIFEST: "application/vnd.apple.mpegurl",
  SEGMENT: "video/MP2T",
  IMAGE: "image/jpeg",
  JSON: "application/json"
}

function hlsContentHeaders(res, path, stat) {
  const ext = path.split(".").slice(-1)[0]
  if (ext === "m3u8" || ext === "ts" || ext === "jpg" || ext === "json") {
    res.setHeader("Access-Control-Allow-Headers", "*")
    res.setHeader("Access-Control-Allow-Method", "GET")
    switch (ext) {
      case ".m3u8":
        res.setHeader("Content-Type", CONTENT_TYPE.MANIFEST)
        break
      case ".ts":
        res.setHeader("Content-Type", CONTENT_TYPE.SEGMENT)
        break
      case ".jpg":
        res.setHeader("Content-Type", CONTENT_TYPE.IMAGE)
        break
      case ".json":
        res.setHeader("Content-Type", CONTENT_TYPE.JSON)
        break
    }
  }
}

const hlsStaticOptions = {
  dotfiles: "ignore",
  etag: false,
  extensions: ["ts", "m3u8", "jpg", "json"],
  index: false,
  maxAge: "1d",
  redirect: false,
  setHeaders: hlsContentHeaders
}

function jsonContentHeaders(req, res, next) {
  res.setHeader("Access-Control-Allow-Headers", "*")
  res.setHeader("Access-Control-Allow-Method", "GET")
  res.setHeader("Content-Type", "application/JSON")
  next()
}

function handleVideoIndex(req, res) {
  const { classroom, date } = req.query

  const qDate = new Date(date)

  if (classroom === undefined) {
    res.sendFile("videos/index.json", {
      root: PUBLIC_PATH
    })
  } else if (date === undefined) {
    res.sendFile(`videos/${classroom}/index.json`, {
      root: PUBLIC_PATH
    })
  } else if (isNaN(qDate.getTime())) {
    return res.json({ error: "date invalid" })
  } else {
    return res.json({ error: "missing req'd query params" })
  }
}

const corsOptions = Object.assign(
  {
    credentials: true,
    origin: "*"
  },
  process.env.ENVIRONMENT !== "production" && {
    // On development, allow origin from any localhost:{port}
    origin: function(origin, callback) {
      if (
        !origin ||
        ["localhost", "127.0.0.1"].indexOf(new URL(origin).hostname) !== -1
      ) {
        callback(null, true)
      } else {
        callback(new Error("Not allowed by CORS"))
      }
    }
  }
)

exports.apply = function(app) {
  const sessionOrJWTAuthMiddleware = [cors(corsOptions), securedSessionOrJWT]

  // Index fetch endpoint
  app.get(
    "/videos",
    ...[
      ...sessionOrJWTAuthMiddleware,
      ...[jsonContentHeaders, handleVideoIndex]
    ]
  )

  // Static file server, serve HLS video assets
  app.use(
    "/videos",
    ...[
      ...sessionOrJWTAuthMiddleware,
      express.static("public/videos", hlsStaticOptions)
    ]
  )
}
