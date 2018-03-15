import React, { Component } from 'react'
import {Link} from 'react-router-dom'
import {format_ts} from '../utils'
import Error from './Error'

class ListView extends Component {
  constructor (props) {
    super(props)
    this.state = {
      items: [],
      error: null,
    }
    this.title = null
    this.url = null
  }

  render_item (item) {
    return <div/>
  }

  async componentDidMount () {
    this.props.setRootState({page_title: this.title, status: 'loading'})
    try {
      const data = await this.props.requests.get(this.url)
      this.setState({items: data.items})
      this.props.setRootState({status: 'ok'})
    } catch (err) {
      this.setState({error: err})
    }
  }

  render () {
    if (this.state.error) {
      return <Error error={this.state.error}/>
    }
    return (
      <ul className="list-group py-3 mx-0">
        {this.state.items.map((item, i) => (
          <li key={i} className="list-group-item">
            {this.render_item(item)}
          </li>
        ))}
      </ul>
    )
  }
}

export class People extends ListView {
  constructor (props) {
    super(props)
    this.title = 'People'
    this.url = '/people/'
  }

  render_item (item) {
    return (
      <Link to={`/people/${item.id}/`} className="d-flex justify-content-between">
        <div>
          <h6 className="my-0">{item.name}</h6>
          <div className="text-muted">
            {item.company_name && <span>{item.company_name}</span>}
          </div>
        </div>
        <span className="float-right text-muted">{format_ts(item.last_seen)}</span>
      </Link>
    )
  }
}

export class Companies extends ListView {
  constructor (props) {
    super(props)
    this.title = 'Companies'
    this.url = '/companies/'
  }

  render_item (item) {
    return (
      <Link to={`/companies/${item.id}/`} className="d-flex justify-content-between">
        <div>
          <h6 className="my-0">{item.name}</h6>
        </div>
        <span className="float-right text-muted">{format_ts(item.created)}</span>
      </Link>
    )
  }
}
