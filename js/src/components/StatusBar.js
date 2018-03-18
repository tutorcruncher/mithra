import React from 'react'

const display_status = {
  loading: 'Loading...',
  offline: 'Offline',
  online: 'Online',
  anon: ' ',
  ok: ' '
}
const StatusBar = ({title, status, alert}) => (
  <div className={`status fixed-top ${status || 'anon'}`}>
    <div className="back"/>
    <div className="container d-flex justify-content-between">
      <span>
        {title}
      </span>
      <span>
        {alert && <span className="mr-3 alert">{alert.msg}</span>}
        <span>
          {display_status[status] || status}
        </span>
      </span>
    </div>
  </div>
)

export default StatusBar
