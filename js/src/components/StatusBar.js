import React, {Component} from 'react'

class StatusBar extends Component {
  render () {
    const display_status = {
      loading: 'Loading...',
      offline: 'Offline',
      online: 'Online',
      anon: ' ',
      ok: ' '
    }
    return (
      <div className={`status fixed-top ${this.props.status || 'anon'}`}>
        <div className="back"/>
        <div className="container d-flex justify-content-between">
          <span>
            {this.props.title}
          </span>
          <span>
            {display_status[this.props.status] || this.props.status}
          </span>
        </div>
      </div>
    )
  }
}

export default StatusBar
