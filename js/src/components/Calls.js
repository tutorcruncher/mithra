import React, { Component } from 'react'
import {Link} from 'react-router-dom'
import {format_ts} from '../utils'
import Error from './Error'

const Bull = () => <span className="px-1">&bull;</span>

class Calls extends Component {
  componentDidMount () {
    this.props.setRootState({page_title: 'Calls'})
  }

  render () {
    if (this.props.error) {
      return <Error error={this.props.error}/>
    }
    if (!this.props.calls.length && this.props.loaded !== null) {
      return this.props.loaded ? (
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
        {this.props.calls.map((call, i) => (
          <li key={i} className={'list-group-item call-list ' + (call.new ? ' new-call': '')}>
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
        ))}
      </ul>
    )
  }
}

export default Calls
