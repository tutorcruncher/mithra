const path = require('path')

module.exports = function override (config, env) {

  // remove the css loader to simplify things
  config.module.rules[1].oneOf = config.module.rules[1].oneOf.filter(function (l) {
    const test = l.test && l.test.toString()
    return test !== /\.css$/
  })
  // compile sass, this comes first and compresses css as well as loading sass/scss
  // https://github.com/facebookincubator/create-react-app/issues/2498
  config.module.rules[1].oneOf.splice(0, 0,
    {
        test: /\.(sass|scss|css)$/,
        use: [
          'style-loader',
          'css-loader',
          {
            loader: 'sass-loader',
            options: {
              outputStyle: 'compressed',
              includePaths: [path.resolve(__dirname, 'node_modules')],
            }
          }
        ]
    },
  )
  // console.dir(config, { depth: 10, colors: true })
  return config
}
