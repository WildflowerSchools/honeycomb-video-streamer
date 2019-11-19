const express = require('express');
const secured = require("./auth").secured;


const CONTENT_TYPE = {
    MANIFEST: 'application/vnd.apple.mpegurl',
    SEGMENT: 'video/MP2T',
}

const port = process.env.SERVICE_PORT ? process.env.SERVICE_PORT : 8000


function contentHeaders(res, path, stat) {
    var ext = path.split('.').slice(-1)[0]
    if(ext == "m3u8" || ext == "ts") {
        res.setHeader('Access-Control-Allow-Origin', '*')
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


exports.apply = function(app) {
    app.use('/videos', secured, express.static('public/videos', options));
}
