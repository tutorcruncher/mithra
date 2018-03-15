import React, { Component } from 'react'
import {Link} from 'react-router-dom'

class Calls extends Component {
  constructor (props) {
    super(props)
    this.state = {
      calls: [],
    }
    this.run_ws = this.run_ws.bind(this)
  }

  componentDidMount () {
    this.props.setRootState({nav_title: 'Calls', status: 'loading'})
    this.run_ws()
  }

  run_ws () {
    const socket = new WebSocket(process.env.REACT_APP_WS_URL)

    socket.onopen = () => {
      console.log('websocket open')
    }

    socket.onclose = e => {
      console.log('websocket closed, reconnecting in 5 seconds', e)
      this.props.setRootState({status: 'offline'})
      setTimeout(this.run_ws, 5000)
    }

    socket.onmessage = e => {
      this.props.setRootState({status: 'online'})
      const data = JSON.parse(e.data)
      console.log('message:', data)
      this.setState({
        calls: Array.isArray(data) ? data : [data].concat(this.state.calls)
      })
    }
  }

  render () {
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
