import {make_url} from './utils'

const notify = async (msg) => {
  if (!('Notification' in window)) {
    console.warn('This browser does not support desktop notification')
  } else if (msg && Notification.permission === 'granted') {
    new Notification(msg)
  } else if (Notification.permission !== 'denied') {
    let perms = await Notification.requestPermission()
    if (msg && perms === 'granted') {
      new Notification(msg)
    }
  }
}
const NEW_TIME = 5000


export default function CallsWebSocket (app) {
  let first_msg = true
  this._connected = false

  this.connect = () => {
    if (this._connected) {
      console.log('ws already connected')
      return
    }
    let ws_url = make_url('/ws/').replace('http', 'ws')
    let socket
    try {
      socket = new WebSocket(ws_url)
    } catch (err) {
      app.setState({ws_error: `WebSocket connection error`})
      return
    }

    socket.onopen = () => {
      console.log('websocket open')
      app.setState({ws_loaded: true})
      this._connected = true
    }

    socket.onclose = e => {
      this._connected = false
      if (e.code === 4403) {
        console.log('not authenticated', e)
        app.setState({auth: false})
      } else {
        console.warn('websocket closed, reconnecting in 5 seconds', e)
        app.setState({status: 'offline'})

        app.setState({ws_calls: []})
        setTimeout(this.connect, 5000)
      }
    }
    socket.onerror = e => {
      console.warn('websocket error:', e)
      app.setState({status: 'offline', ws_error: `WebSocket error`})
    }
    socket.onmessage = on_message
  }

  const on_message = event => {
    first_msg && notify()
    first_msg = false
    app.setState({status: 'online'})
    const data = JSON.parse(event.data)
    const new_call = !Array.isArray(data)
    app.setState({ws_error: null})
    update_calls(new_call ? [data].concat(app.state.ws_calls) : data)
    if (new_call) {
      let msg = ''
      if (data.person_name) {
        msg += data.has_support ? '✔ ' : '✘ '
        msg += data.person_name
        if (data.company) {
          msg += ` (${data.company})`
        }
        msg += ' on '
      }
      msg += data.number
      if (data.country) {
        msg += ` (${data.country})`
      }
      notify('📞 ' + msg)
      app.setState({status_alert: {time: new Date(), msg: 'Incoming Call: ' + msg}})
    }
    // to change new where applicable
    setTimeout(() => update_calls(), NEW_TIME + 100)
  }

  const update_calls = calls => {
    const now = new Date()
    calls = calls || app.state.ws_calls
    app.setState({ws_calls: calls.map(c => Object.assign(c, {new: (now - new Date(c.ts)) < NEW_TIME}))})
    if (app.state.status_alert && (now - app.state.status_alert.time) > NEW_TIME) {
      app.setState({status_alert: null})
    }
  }

  this.connect()
  setTimeout(() => {
   !app.state.ws_loaded && app.setState({ws_loaded: false})
  }, 500)
}
