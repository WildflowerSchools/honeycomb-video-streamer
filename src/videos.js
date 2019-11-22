const express = require('express');
const cors = require('cors');
const secured = require("./auth").secured;


const CONTENT_TYPE = {
    MANIFEST: 'application/vnd.apple.mpegurl',
    SEGMENT: 'video/MP2T',
}

function contentHeaders(res, path, stat) {
    const ext = path.split('.').slice(-1)[0]
    if (ext === "m3u8" || ext === "ts") {
        res.setHeader('Access-Control-Allow-Headers', '*')
        res.setHeader('Access-Control-Allow-Method', 'GET')
        switch (ext) {
            case '.m3u8':
                res.setHeader('Content-Type', CONTENT_TYPE.MANIFEST)
                break
            case '.ts':
                res.setHeader('Content-Type', CONTENT_TYPE.SEGMENT)
                break
        }
    }
}

const options = {
  dotfiles: 'ignore',
  etag: false,
  extensions: ['ts', 'm3u8'],
  index: false,
  maxAge: '1d',
  redirect: false,
  setHeaders: contentHeaders,
}

const corsOptions = Object.assign({
    credentials: true,
    origin: '*'
  }, process.env.ENVIRONMENT !== "production" &&
    {
      // On development, allow origin from any localhost:{port}
      origin: function (origin, callback) {
        if (!origin || ['localhost', '127.0.0.1'].indexOf(new URL(origin).hostname) !== -1) {
          callback(null, true)
        } else {
          callback(new Error('Not allowed by CORS'))
        }
      }
    }
)

exports.apply = function(app) {
    app.use('/videos', cors(corsOptions), secured, express.static('public/videos', options));
}
