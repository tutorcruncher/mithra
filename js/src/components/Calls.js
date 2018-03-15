import React, { Component } from 'react'
import {Link} from 'react-router-dom'

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

class Calls extends Component {
  constructor (props) {
    super(props)
    this.state = {
      calls: [],
      error: null
    }
    this.run_ws = this.run_ws.bind(this)
  }

  componentDidMount () {
    notify()
    this.props.setRootState({nav_title: 'Calls', status: 'loading'})
    this.run_ws()
  }

  run_ws () {
    let ws_url = process.env.REACT_APP_WS_URL
    if (ws_url.startsWith('/')) {
      ws_url = window.location.origin.replace('http', 'ws') + ws_url
    }
    let socket
    try {
      socket = new WebSocket(ws_url)
    } catch (err) {
      this.setState({error: `WebSocket connection error: ${err}`})
      return
    }

    socket.onopen = () => {
      console.log('websocket open')
    }

    socket.onclose = e => {
      console.log('websocket closed, reconnecting in 5 seconds', e)
      this.props.setRootState({status: 'offline'})
      this.setState({calls: []})
      setTimeout(this.run_ws, 5000)
    }

    socket.onerror = e => {
      console.warn('websocket error:', e)
      this.setState({error: `WebSocket error`})
    }

    socket.onmessage = e => {
      this.props.setRootState({status: 'online'})
      const data = JSON.parse(e.data)
      const new_call = !Array.isArray(data)
      this.setState({
        calls: new_call ? [data].concat(this.state.calls) : data
      })
      if (new_call) {
        this.setState({
          calls: [data].concat(this.state.calls)
        })
        let msg = 'Incoming call from '
        if (data.person_name) {
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
        notify(msg)
      }
    }
  }

  render () {
    if (this.state.error) {
      return (
        <div>
          <h3>Error:</h3>
          <p>{this.state.error}</p>
        </div>
      )
    }
    return (
      <ul className="list-group py-3 mx-0">
        {this.state.calls.map((call, i) => (
          <li key={i} className="list-group-item">
            <Link to={`/call/${call.id}/`} className="d-flex justify-content-between list-link">
              <div>
                <h6 className="my-0">{call.number}</h6>
                <small className="text-muted">
                  {call.person_name}
                  {call.company && <span> ({call.company})</span>}
                  &nbsp;
                  </small>
              </div>
              <span className="text-muted float-right">{call.ts}</span>
            </Link>
          </li>
        ))}
      </ul>
    )
  }
}

export default Calls
