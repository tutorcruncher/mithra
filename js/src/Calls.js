import React, { Component } from 'react'

const Call = ({data}) => (
  <div>
    <b>{data.number}</b> {data.name} ({data.company})
  </div>
)

class Calls extends Component {
  constructor (props) {
    super(props)
    this.state = {
      calls: [],
      status: 'Loading...'
    }
    this.run_ws = this.run_ws.bind(this)
  }

  componentDidMount () {
    this.run_ws()
  }

  run_ws () {
    const socket = new WebSocket(process.env.REACT_APP_WS_URL)

    socket.onopen = () => {
      console.log('websocket open')
      this.setState({status: 'Online'})
    }

    socket.onclose = e => {
      console.log('websocket closed, reconnecting in 5 seconds', e)
      this.setState({status: 'Disconnected'})
      setTimeout(this.run_ws, 5000)
    }

    socket.onmessage = e => {
      const data = JSON.parse(e.data)
      console.log('message:', data)
      this.setState({
        calls: Array.isArray(data) ? data : this.state.calls.concat([data])
      })
    }
  }

  render () {
    return (
      <div>
        <div className="status">
          {this.state.status}
        </div>
        {this.state.calls.map((call, i) => (
          <Call key={i} data={call}/>
        ))}
      </div>
    )
  }
}

export default Calls
