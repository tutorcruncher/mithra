import React, { Component } from 'react'
import {Link} from 'react-router-dom'
import {make_url, format_ts} from '../utils'
import Error from './Error'

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
const NEW_TIME = 3000
const Bull = () => <span className="px-1">&bull;</span>

const Call = ({call}) => {
  return (
    <li className={'list-group-item call-list ' + (call.new ? ' new-call': '')}>
      <Link to={`/calls/${call.id}/`} className="d-flex justify-content-between call-link">
        <div>
          <h6 className="my-0">{call.number} {call.has_support && <span>✔</span>}</h6>
          <small>
            {call.person_name ?
            <span className="text-muted">
              {call.person_name} <Bull/>
              {call.company} {call.company && <Bull/>}
              <span>{call.has_support ? 'has support' : 'no support'}</span>
            </span>
            : <span>&nbsp;</span>}
          </small>
        </div>
        <span className="float-right text-muted">{format_ts(call.ts)}</span>
      </Link>
    </li>
  )
}

class Calls extends Component {
  constructor (props) {
    super(props)
    this.state = {
      calls: [],
      loaded: null,
      error: null,
    }
    this.run_ws = this.run_ws.bind(this)
    this.on_message = this.on_message.bind(this)
    this.update_calls = this.update_calls.bind(this)
    this.first_msg = true
    this.mounted = false
  }

  componentDidMount () {
    this.mounted = true
    this.props.setRootState({page_title: 'Calls', status: 'loading'})
    this.run_ws()
    setTimeout(() => {
      this.mounted && this.setState({loaded: false})
    }, 500)
  }

  componentWillUnmount () {
    this.mounted = false
  }

  run_ws () {
    let ws_url = make_url('/ws/').replace('http', 'ws')
    let socket
    try {
      socket = new WebSocket(ws_url)
    } catch (err) {
      this.setState({error: err})
      return
    }

    socket.onopen = () => {
      console.log('websocket open')
      this.setState({loaded: true})
    }

    socket.onclose = e => {
      if (e.code === 4403) {
        console.log('not authenticated', e)
        this.props.setRootState({auth: false})
      } else {
        console.log('websocket closed, reconnecting in 5 seconds', e)
        this.props.setRootState({status: 'offline'})

        if (this.mounted) {
          this.setState({calls: []})
          setTimeout(this.run_ws, 5000)
        }
      }
    }

    socket.onerror = e => {
      console.warn('websocket error:', e)
      this.mounted && this.setState({error: `WebSocket error`})
    }

    socket.onmessage = this.on_message
  }

  on_message (event) {
    if (!this.mounted) {
      return
    }
    this.first_msg && notify()
    this.first_msg = false
    this.props.setRootState({status: 'online'})
    const data = JSON.parse(event.data)
    const new_call = !Array.isArray(data)
    this.setState({error: null})
    this.update_calls(new_call ? [data].concat(this.state.calls) : data)
    if (new_call) {
      let msg = '📞 '
      msg += data.has_support ? '✔ ' : '✘ '
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
    // to change new where applicable
    setTimeout(() => this.update_calls(), NEW_TIME + 100)
  }

  update_calls (calls) {
    if (!this.mounted) {
      return
    }
    const now = new Date()
    calls = calls || this.state.calls
    this.setState({
      calls: calls.map(c => {
        const age = now - new Date(c.ts)
        c.new = age < NEW_TIME
        return c
      })
    })
  }

  render () {
    if (this.state.error) {
      return <Error error={this.state.error}/>
    }
    if (!this.state.calls.length && this.state.loaded !== null) {
      return this.state.loaded ? (
        <div className="box">
          No calls recorded.
        </div>
      ) : (
        <div className="box">
          <div className="loader"/>
          <div className="text-center h3">Loading...</div>
        </div>
      )
    }
    return (
      <ul className="list-group py-3 mx-0">
        {this.state.calls.map((call, i) => (
          <Call key={i} call={call}/>
        ))}
      </ul>
    )
  }
}

export default Calls
