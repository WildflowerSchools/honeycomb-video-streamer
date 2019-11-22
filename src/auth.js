const express = require("express")
const router = express.Router()
const expressSession = require("express-session")
const passport = require("passport")
const Auth0Strategy = require("passport-auth0")
const util = require("util")
const querystring = require("querystring")
const jwt = require("express-jwt")
const jwksRsa = require("jwks-rsa")

const session = {
  secret: "CCgp89X4gQmXtdqav9BxGxNP3DuA",
  cookie: Object.assign(
    { secure: true, sameSite: "strict" },
    process.env.ENVIRONMENT !== "production" && {
      domain: "localhost",
      sameSite: "none"
    }
  ),
  resave: false,
  saveUninitialized: false
}

const port = process.env.SERVICE_PORT ? process.env.SERVICE_PORT : 8000

const authConfig = {
  domain: process.env.AUTH0_DOMAIN,
  audience: process.env.AUTH0_AUDIENCE,
  clientID: process.env.AUTH0_CLIENT_ID,
  clientSecret: process.env.AUTH0_CLIENT_SECRET,
  callbackURL: process.env.AUTH0_CALLBACK_URL
    ? process.env.AUTH0_CALLBACK_URL
    : `https://localhost:${port}/callback`
}

const sessionStrategy = new Auth0Strategy(
  {
    domain: authConfig.domain,
    clientID: authConfig.clientID,
    clientSecret: authConfig.clientSecret,
    callbackURL: authConfig.callbackURL
  },
  function(accessToken, refreshToken, extraParams, profile, done) {
    /**
     * Access tokens are used to authorize users to an API
     * (resource server)
     * accessToken is the token to call the Auth0 API
     * or a secured third-party API
     * extraParams.id_token has the JSON Web Token
     * profile has all the information from the user
     */
    return done(null, profile)
  }
)

router.get(
  "/login",
  passport.authenticate("auth0", {
    scope: "openid email profile"
  }),
  (req, res) => {
    res.redirect("/")
  }
)

router.get("/callback", (req, res, next) => {
  passport.authenticate("auth0", (err, user, info) => {
    if (err) {
      return next(err)
    }
    if (!user) {
      return res.redirect("/login")
    }
    req.logIn(user, err => {
      if (err) {
        return next(err)
      }
      const returnTo = req.session.returnTo
      delete req.session.returnTo
      res.redirect(returnTo || "/")
    })
  })(req, res, next)
})

router.get("/logout", (req, res) => {
  req.logOut()

  let returnTo = req.protocol + "://" + req.hostname
  const port = req.connection.localPort

  if (port !== undefined && port !== 80 && port !== 443) {
    returnTo =
      process.env.NODE_ENV === "production"
        ? `${returnTo}/`
        : `${returnTo}:${port}/`
  }

  const logoutURL = new URL(
    util.format("https://%s/logout", process.env.AUTH0_DOMAIN)
  )
  const searchString = querystring.stringify({
    client_id: process.env.AUTH0_CLIENT_ID,
    returnTo: returnTo
  })
  logoutURL.search = searchString

  res.redirect(logoutURL)
})

exports.apply = function(app) {
  app.use(expressSession(session))
  passport.use(sessionStrategy)
  app.use(passport.initialize())
  app.use(passport.session())
  app.use("/", router)

  passport.serializeUser((user, done) => {
    done(null, user)
  })

  passport.deserializeUser((user, done) => {
    done(null, user)
  })
}

exports.securedSession = (req, res, next) => {
  if (req.user) {
    return next()
  }
  req.session.returnTo = req.originalUrl
  res.redirect("/login")
}

// Define middleware that validates incoming bearer tokens
// using JWKS from wildflowerschools.auth0.com
exports.securedJWT = jwt({
  secret: jwksRsa.expressJwtSecret({
    cache: true,
    rateLimit: true,
    jwksRequestsPerMinute: 5,
    jwksUri: `https://${authConfig.domain}/.well-known/jwks.json`
  }),

  audience: authConfig.audience,
  issuer: `https://${authConfig.domain}/`,
  algorithm: ["RS256"]
})
